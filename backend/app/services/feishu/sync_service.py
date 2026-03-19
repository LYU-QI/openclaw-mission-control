"""Feishu Bitable sync orchestration service."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.secrets import decrypt_secret
from app.core.time import utcnow
from app.models.agents import Agent
from app.models.feishu_sync import FeishuSyncConfig, FeishuTaskMapping
from app.models.tasks import Task
from app.services.activity_log import record_activity
from app.services.feishu.client import FeishuClient
from app.services.feishu.conflict_resolver import ConflictResolver, SyncSideState
from app.services.feishu.field_mapper import FieldMapper

if TYPE_CHECKING:
    from app.services.openclaw.agent_invoker import AgentInvoker

logger = logging.getLogger(__name__)


def _templates_root() -> Path:
    return Path(__file__).resolve().parents[3] / "templates"


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_templates_root()),
        autoescape=False,
        keep_trailing_newline=True,
    )


def _compute_hash(fields: dict[str, Any]) -> str:
    raw = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SyncService:
    """Orchestrates bidirectional sync between Feishu Bitable and Mission Control."""

    def __init__(self, session: AsyncSession, config: FeishuSyncConfig) -> None:
        self.session = session
        self.config = config
        self.client = FeishuClient(config.app_id, decrypt_secret(config.app_secret_encrypted))
        self.mapper = FieldMapper(config.field_mapping)
        self.conflict_resolver = ConflictResolver()
        self.board_mapping = config.board_mapping or {}

    def _get_board_id_for_task(self, feishu_fields: dict[str, Any]) -> UUID | None:
        """Determine the board_id for a task based on Feishu fields and board_mapping."""
        # First, check if field_mapping contains a board field (e.g., "看板" -> "board")
        board_field_key = None
        for feishu_key, mc_key in self.mapper.mapping.items():
            if mc_key == "board":
                board_field_key = feishu_key
                break

        if board_field_key:
            board_name = feishu_fields.get(board_field_key)
            if board_name and board_name in self.board_mapping:
                return UUID(self.board_mapping[board_name])

        # Fall back to default board_id from config
        return self.config.board_id

    async def _assign_review_task_to_lead(self, task: Task) -> None:
        """Assign a review-status task to the board's lead agent."""
        if task.status != "review" or task.board_id is None:
            return
        await self._assign_task_to_orchestrator(task)

    async def _assign_task_to_orchestrator(self, task: Task) -> None:
        """Assign a task to the Orchestrator agent (not Lead Agent)."""
        if task.board_id is None:
            return

        # First try to find Orchestrator by system_role (not board-specific)
        # System role agents have board_id=None but have system_role set
        result = await self.session.exec(
            select(Agent)
            .where(Agent.system_role == "orchestrator")
            .where(Agent.gateway_id.in_(
                select(Agent.gateway_id).where(Agent.board_id == task.board_id)
            ))
        )
        orchestrator = result.first()

        # Fallback: find Orchestrator by name pattern (board-specific)
        if not orchestrator:
            result = await self.session.exec(
                select(Agent)
                .where(col(Agent.board_id) == task.board_id)
                .where(Agent.name.ilike("%Orchestrator%"))
            )
            orchestrator = result.first()

        if orchestrator:
            task.assigned_agent_id = orchestrator.id
            logger.info(
                "feishu.sync.assign_to_orchestrator task_id=%s orchestrator_id=%s",
                task.id,
                orchestrator.id,
            )
        else:
            # Fallback to Lead Agent if no Orchestrator found
            result = await self.session.exec(
                select(Agent)
                .where(col(Agent.board_id) == task.board_id)
                .where(col(Agent.is_board_lead) == True)
            )
            lead = result.first()
            if lead:
                task.assigned_agent_id = lead.id
                logger.warning(
                    "feishu.sync.assign_fallback_to_lead task_id=%s lead_id=%s (no orchestrator found)",
                    task.id,
                    lead.id,
                )

    async def _auto_create_and_dispatch_mission(self, task: Task) -> None:
        """Auto-create and dispatch a mission for a newly synced task."""
        if not self.config.auto_dispatch:
            return

        # Lazy import to avoid circular dependency
        from app.services.missions.orchestrator import MissionOrchestrator

        if task.board_id is None:
            logger.warning(
                "feishu.sync.auto_dispatch.skip no_board task_id=%s",
                task.id,
            )
            return

        # Assign task to Orchestrator if not already assigned
        if task.assigned_agent_id is None:
            await self._assign_task_to_orchestrator(task)
            self.session.add(task)
            await self.session.flush()

        try:
            orchestrator = MissionOrchestrator(self.session)
            approval_policy = getattr(self.config, "default_approval_policy", "auto") or "auto"
            mission = await orchestrator.create_mission(
                task_id=task.id,
                board_id=task.board_id,
                agent_id=task.assigned_agent_id,
                goal=task.description or f"处理任务: {task.title}",
                approval_policy=approval_policy,
            )
            await orchestrator.dispatch_mission(mission.id)
            logger.info(
                "feishu.sync.auto_dispatch.success task_id=%s mission_id=%s",
                task.id,
                mission.id,
            )
            record_activity(
                self.session,
                event_type="feishu_sync_auto_dispatch",
                message=f"自动为任务创建并下发 Mission: {task.title}",
                task_id=task.id,
                board_id=task.board_id,
            )
        except Exception as exc:
            logger.error(
                "feishu.sync.auto_dispatch.failed task_id=%s error=%s",
                task.id,
                str(exc),
            )
            record_activity(
                self.session,
                event_type="feishu_sync_auto_dispatch_failed",
                message=f"自动下发 Mission 失败: {str(exc)[:100]}",
                task_id=task.id,
                board_id=task.board_id,
            )

    def _has_local_conflict(self, *, mapping: FeishuTaskMapping, task: Task, new_hash: str) -> bool:
        if mapping.sync_hash == new_hash:
            return False

        feishu_state = SyncSideState(
            updated_at=mapping.last_feishu_update,
            checksum=new_hash,
        )
        mission_control_state = SyncSideState(
            updated_at=task.updated_at,
            checksum=mapping.sync_hash,
        )
        winner = self.conflict_resolver.resolve(
            feishu=feishu_state,
            mission_control=mission_control_state,
        )
        if winner != "mission_control":
            return False
        if mapping.last_feishu_update is None:
            return True
        return task.updated_at > mapping.last_feishu_update

    async def _record_conflict(
        self,
        *,
        record_id: str,
        task_id: Task | None,
    ) -> None:
        record_activity(
            self.session,
            event_type="feishu_sync_conflict",
            message=f"Skipped Feishu record {record_id} because Mission Control has newer local changes.",
            task_id=task_id.id if task_id is not None else None,
            board_id=self.config.board_id,
        )

    async def resolve_conflict_keep_local(self, mapping: FeishuTaskMapping) -> FeishuTaskMapping:
        """Resolve a sync conflict by keeping Mission Control as source of truth."""
        task = await Task.objects.by_id(mapping.task_id).first(self.session)
        if task is None:
            raise RuntimeError(f"Task {mapping.task_id} not found for mapping {mapping.id}")

        feishu_fields = self.mapper.to_feishu(task)
        self.client.update_bitable_record(
            self.config.bitable_app_token,
            self.config.bitable_table_id,
            mapping.feishu_record_id,
            feishu_fields,
        )
        mapping.sync_hash = _compute_hash(feishu_fields)
        mapping.last_feishu_update = utcnow()
        mapping.last_mc_update = task.updated_at
        mapping.updated_at = utcnow()
        self.session.add(mapping)
        record_activity(
            self.session,
            event_type="feishu_sync_conflict_resolved_local",
            message=f"Resolved Feishu sync conflict for {mapping.feishu_record_id} by keeping Mission Control changes.",
            task_id=task.id,
            board_id=self.config.board_id,
        )
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def resolve_conflict_accept_feishu(self, mapping: FeishuTaskMapping) -> FeishuTaskMapping:
        """Resolve a sync conflict by accepting current Feishu record values."""
        task = await Task.objects.by_id(mapping.task_id).first(self.session)
        if task is None:
            raise RuntimeError(f"Task {mapping.task_id} not found for mapping {mapping.id}")

        resp = self.client.get_bitable_record(
            self.config.bitable_app_token,
            self.config.bitable_table_id,
            mapping.feishu_record_id,
        )
        item = resp.get("data", {}).get("record", {})
        fields: dict[str, Any] = item.get("fields", {})
        task_data = self.mapper.to_mc(fields)
        for key, value in task_data.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)
        task.updated_at = utcnow()
        self.session.add(task)

        mapping.sync_hash = _compute_hash(fields)
        mapping.last_feishu_update = utcnow()
        mapping.last_mc_update = task.updated_at
        mapping.updated_at = utcnow()
        self.session.add(mapping)
        record_activity(
            self.session,
            event_type="feishu_sync_conflict_resolved_feishu",
            message=f"Resolved Feishu sync conflict for {mapping.feishu_record_id} by accepting Feishu changes.",
            task_id=task.id,
            board_id=self.config.board_id,
        )
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def pull_from_feishu(self) -> dict[str, int]:
        """Pull records from Feishu and create/update local tasks."""
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "conflicts": 0,
        }

        try:
            field_resp = self.client.list_bitable_fields(
                self.config.bitable_app_token,
                self.config.bitable_table_id,
            )
            bitable_fields = field_resp.get("data", {}).get("items", [])
            actual_field_names = {f.get("field_name") for f in bitable_fields}

            missing_fields = []
            for expected_feishu_key in self.mapper.mapping.keys():
                if expected_feishu_key not in actual_field_names:
                    missing_fields.append(expected_feishu_key)

            if missing_fields:
                logger.warning(
                    "feishu.sync.missing_fields config_id=%s missing=%s",
                    self.config.id,
                    missing_fields,
                )
                record_activity(
                    self.session,
                    event_type="feishu_sync_warning",
                    message=(
                        f"警告：飞书数据表结构发生变更，找不到映射配置中期待的以下字段："
                        f"{', '.join(missing_fields)}。请检查飞书表结构或修改映射配置。"
                    ),
                    board_id=self.config.board_id,
                )
        except Exception as exc:
            logger.warning("feishu.sync.detect_fields_failed reason=%s", str(exc))

        page_token: str | None = None
        while True:
            resp = self.client.list_bitable_records(
                self.config.bitable_app_token,
                self.config.bitable_table_id,
                page_token=page_token,
            )
            data = resp.get("data", {})
            items: list[dict[str, Any]] = data.get("items", [])

            for item in items:
                record_id: str = item.get("record_id", "")
                fields: dict[str, Any] = item.get("fields", {})
                stats["processed"] += 1

                # Check if mapping already exists
                stmt = select(FeishuTaskMapping).where(
                    FeishuTaskMapping.sync_config_id == self.config.id,
                    FeishuTaskMapping.feishu_record_id == record_id,
                )
                result = await self.session.exec(stmt)
                mapping = result.first()

                task_data = self.mapper.to_mc(fields)
                new_hash = _compute_hash(fields)

                if mapping is None:
                    # Create new task
                    board_id = self._get_board_id_for_task(fields)
                    task = Task(
                        board_id=board_id,
                        title=task_data.get("title", "Untitled"),
                        description=task_data.get("description"),
                        status=task_data.get("status", "inbox"),
                        priority=task_data.get("priority", "medium"),
                        external_source="feishu",
                        external_id=record_id,
                        owner_name=task_data.get("owner_name"),
                        milestone=task_data.get("milestone"),
                    )
                    self.session.add(task)
                    await self.session.flush()

                    new_mapping = FeishuTaskMapping(
                        sync_config_id=self.config.id,
                        feishu_record_id=record_id,
                        task_id=task.id,
                        last_feishu_update=utcnow(),
                        sync_hash=new_hash,
                    )
                    self.session.add(new_mapping)
                    stats["created"] += 1

                    # Assign to lead if task starts in review
                    await self._assign_review_task_to_lead(task)

                    # Auto-create and dispatch mission if enabled
                    if self.config.auto_dispatch:
                        await self._auto_create_and_dispatch_mission(task)
                elif mapping.sync_hash == new_hash:
                    stats["skipped"] += 1
                elif mapping.sync_hash != new_hash:
                    # Update existing task
                    task = await Task.objects.by_id(mapping.task_id).first(self.session)
                    if task:
                        if self._has_local_conflict(mapping=mapping, task=task, new_hash=new_hash):
                            stats["skipped"] += 1
                            stats["conflicts"] += 1
                            await self._record_conflict(record_id=record_id, task_id=task)
                            continue
                        for key, value in task_data.items():
                            if hasattr(task, key) and value is not None:
                                setattr(task, key, value)
                        task.updated_at = utcnow()
                        self.session.add(task)

                    mapping.sync_hash = new_hash
                    mapping.last_feishu_update = utcnow()
                    mapping.updated_at = utcnow()
                    self.session.add(mapping)
                    stats["updated"] += 1

            if not data.get("has_more", False):
                break
            page_token = data.get("page_token")

        # Update config status
        self.config.last_sync_at = utcnow()
        self.config.sync_status = "idle"
        self.config.last_error = None
        self.config.updated_at = utcnow()
        self.session.add(self.config)

        record_activity(
            self.session,
            event_type="feishu_sync_pull",
            message=(
                f"Synced {stats['processed']} records "
                f"({stats['created']} new, {stats['updated']} updated, "
                f"{stats['skipped']} skipped, {stats['conflicts']} conflicts)"
            ),
            board_id=self.config.board_id,
        )

        await self.session.commit()
        return stats

    async def push_to_feishu(
        self,
        task_id: UUID,
    ) -> bool:
        """Push task results back to a Feishu Bitable record."""
        stmt = select(FeishuTaskMapping).where(
            FeishuTaskMapping.sync_config_id == self.config.id,
            FeishuTaskMapping.task_id == task_id,
        )
        result = await self.session.exec(stmt)
        mapping = result.first()
        if mapping is None:
            logger.warning("No Feishu mapping found for task %s", task_id)
            return False

        task = await Task.objects.by_id(task_id).first(self.session)
        if task is None:
            return False

        feishu_fields = self.mapper.to_feishu(task)
        self.client.update_bitable_record(
            self.config.bitable_app_token,
            self.config.bitable_table_id,
            mapping.feishu_record_id,
            feishu_fields,
        )

        mapping.last_mc_update = utcnow()
        mapping.updated_at = utcnow()
        self.session.add(mapping)

        record_activity(
            self.session,
            event_type="feishu_sync_push",
            message=f"Pushed results for task {task_id} to Feishu",
            task_id=task_id,
            board_id=task.board_id,
        )

        await self.session.commit()
        return True

    async def _invoke_sync_agent(
        self,
        operation: str,
        records: list[dict[str, Any]] | None = None,
        tasks: list[Task] | None = None,
    ) -> dict[str, Any]:
        """Invoke Sync Agent to perform sync operations via Gateway RPC.

        This is an alternative to direct sync - it calls the Sync Agent
        which then performs the sync operations.

        Args:
            operation: The operation to perform (pull, push)
            records: For pull operations, the Feishu records to process
            tasks: For push operations, the tasks to push to Feishu

        Returns:
            Dict with keys: success (bool), result (dict), error (str)
        """
        # Check if agent-based sync is enabled
        if not settings.enable_agent_sync:
            return {
                "success": False,
                "result": None,
                "error": "Agent-based sync is disabled (ENABLE_AGENT_SYNC=false)",
            }

        try:
            from app.services.openclaw.agent_invoker import AgentInvoker

            invoker = AgentInvoker(self.session)

            # Render the task instruction template
            template = _template_env().get_template("agent_tasks/sync_agent_task.md.j2")

            # Build template context
            context = {
                "operation": operation,
                "config_id": str(self.config.id),
                "feishu_app_token": self.config.app_id,
                "bitable_table_id": self.config.bitable_table_id,
            }

            if operation == "pull" and records:
                context["records_count"] = len(records)

            if operation == "push" and tasks:
                context["tasks"] = [
                    {
                        "id": str(t.id),
                        "title": t.title,
                        "status": t.status,
                        "result_summary": t.result_summary or "",
                        "result_risk": t.result_risk or "",
                        "result_next_action": t.result_next_action or "",
                    }
                    for t in tasks
                ]

            instruction = template.render(**context)

            # Invoke the Sync Agent
            result = await invoker.invoke_system_agent(
                organization_id=self.config.organization_id,
                system_role="sync_agent",
                instruction=instruction,
            )

            if result.get("success"):
                logger.info("sync_agent.operation_completed operation=%s", operation)
                return {"success": True, "result": result, "error": None}
            else:
                logger.warning(
                    "sync_agent.operation_failed operation=%s error=%s",
                    operation,
                    result.get("error"),
                )
                return {"success": False, "result": None, "error": result.get("error")}

        except Exception as e:
            logger.exception("Failed to invoke Sync Agent: %s", e)
            return {"success": False, "result": None, "error": str(e)}
