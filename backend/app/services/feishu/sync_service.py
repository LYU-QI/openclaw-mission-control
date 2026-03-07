"""Feishu Bitable sync orchestration service."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.core.secrets import decrypt_secret
from app.models.feishu_sync import FeishuSyncConfig, FeishuTaskMapping
from app.models.tasks import Task
from app.services.activity_log import record_activity
from app.services.feishu.client import FeishuClient
from app.services.feishu.field_mapper import FieldMapper

logger = logging.getLogger(__name__)


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

    async def pull_from_feishu(self) -> dict[str, int]:
        """Pull records from Feishu and create/update local tasks."""
        stats = {"processed": 0, "created": 0, "updated": 0}

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
                    task = Task(
                        board_id=self.config.board_id,
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
                elif mapping.sync_hash != new_hash:
                    # Update existing task
                    task = await Task.objects.by_id(mapping.task_id).first(self.session)
                    if task:
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
            message=f"Synced {stats['processed']} records ({stats['created']} new, {stats['updated']} updated)",
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
