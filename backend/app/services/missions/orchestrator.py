"""Mission lifecycle orchestration and status tracking."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.core.config import settings
from app.models.approvals import Approval
from app.models.agents import Agent
from app.models.boards import Board
from app.models.feishu_sync import FeishuSyncConfig
from app.models.missions import Mission, MissionSubtask
from app.models.tasks import Task
from app.services.activity_log import record_activity
from app.services.feishu.writeback_service import WritebackService
from app.services.missions.approval_gate import ApprovalGate
from app.services.missions.constraint_resolver import ConstraintResolver
from app.services.missions.goal_builder import GoalBuilder
from app.services.missions.status_machine import (
    MISSION_STATUS_AGGREGATING,
    MISSION_STATUS_CANCELLED,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_DISPATCHED,
    MISSION_STATUS_FAILED,
    MISSION_STATUS_PENDING,
    MISSION_STATUS_PENDING_APPROVAL,
    MISSION_STATUS_RUNNING,
    SUBTASK_STATUS_COMPLETED,
    SUBTASK_STATUS_FAILED,
    SUBTASK_STATUS_PENDING,
    SUBTASK_STATUS_RUNNING,
    SUBTASK_TERMINAL_STATUSES,
    ensure_mission_transition,
    ensure_subtask_transition,
)
from app.services.missions.status_tracker import MissionStatusTracker
from app.services.notification.notification_service import NotificationService
from app.services.openclaw.aggregator.aggregator import ResultAggregator
from app.services.openclaw.context.loader import ContextLoader
from app.services.openclaw.decomposer.decomposer import TaskDecomposer
from app.services.openclaw.subagent_dispatch import SubagentDispatchService

logger = logging.getLogger(__name__)


class MissionOrchestrator:
    """Creates, dispatches, and manages the lifecycle of Missions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.goal_builder = GoalBuilder()
        self.constraint_resolver = ConstraintResolver()
        self.approval_gate = ApprovalGate(session)
        self.status_tracker = MissionStatusTracker(session)
        self.notification_service = NotificationService(session)
        self.context_loader = ContextLoader()
        self.decomposer = TaskDecomposer()
        self.aggregator = ResultAggregator()
        self._orchestrator_agent_id: UUID | None = None

    async def _notify_mission_event(self, mission: Mission, event_type: str, message: str) -> None:
        board = await Board.objects.by_id(mission.board_id).first(self.session)
        if board is None:
            return

        from app.models.tasks import Task
        from app.models.missions import MissionSubtask
        task = await Task.objects.by_id(mission.task_id).first(self.session)

        # Build extra payload with task results if available
        extra = {
            "mission_id": str(mission.id),
            "task_id": str(mission.task_id),
            "task_title": task.title if task else "未知任务",
        }

        # Add result fields if task has them
        if task:
            if task.result_summary:
                extra["result_summary"] = task.result_summary
            if task.result_risk:
                extra["risk"] = task.result_risk
            if task.result_next_action:
                extra["next_action"] = task.result_next_action

        # Fetch subtask results for mission_completed event
        if event_type == "mission_completed" and task:
            subtask_results = await self._get_subtask_results(mission.id)
            if subtask_results:
                extra["subtask_results"] = subtask_results

        await self.notification_service.notify(
            organization_id=board.organization_id,
            board_id=board.id,
            event_type=event_type,
            message=message,
            extra=extra,
        )

    async def _get_subtask_results(self, mission_id: UUID) -> str | None:
        """Get formatted subtask results for notification."""
        from app.models.missions import MissionSubtask

        # Get base URL for artifacts
        from app.core.config import settings
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")

        result = await self.session.exec(
            select(MissionSubtask)
            .where(MissionSubtask.mission_id == mission_id)
            .where(MissionSubtask.status == "completed")
            .order_by(MissionSubtask.order)
        )
        subtasks = result.all()

        if not subtasks:
            return None

        lines = []
        links = []  # Collect artifacts/links

        for subtask in subtasks:
            if subtask.result_summary:
                # Clean up the result summary (remove newlines for card display)
                summary = subtask.result_summary.replace("\n", " ").strip()
                if len(summary) > 300:
                    summary = summary[:300] + "..."
                lines.append(f"• {subtask.label}: {summary}")

            # Extract artifacts/links from result_evidence
            if subtask.result_evidence:
                import json
                try:
                    evidence = json.loads(subtask.result_evidence) if isinstance(subtask.result_evidence, str) else subtask.result_evidence
                    if "artifacts" in evidence:
                        for artifact in evidence["artifacts"]:
                            if isinstance(artifact, str):
                                # Check if it's a URL
                                if "http" in artifact:
                                    # Extract URL from format "Title - URL"
                                    parts = artifact.split(" - ")
                                    if len(parts) >= 2:
                                        links.append((parts[0].strip(), parts[-1].strip()))
                                    else:
                                        links.append((artifact[:50], artifact))
                                else:
                                    # Local file path - convert to accessible URL
                                    # Common extensions that should be accessible in browser
                                    if any(ext in artifact.lower() for ext in ['.html', '.htm', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.json', '.md', '.py']):
                                        # Convert local path to artifacts URL
                                        filename = artifact.split('/')[-1]
                                        artifact_url = f"{base_url}/api/v1/artifacts/{filename}"
                                        links.append((f"打开 {filename}", artifact_url))
                                    else:
                                        links.append((artifact[:50], artifact))
                            elif isinstance(artifact, dict):
                                # Handle dict format
                                name = artifact.get("name", artifact.get("title", "Artifact"))
                                url = artifact.get("url", artifact.get("path", ""))
                                if url:
                                    # Check if it's a local file that needs conversion
                                    if not url.startswith("http") and any(ext in url.lower() for ext in ['.html', '.htm', '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.md', '.py']):
                                        filename = url.split('/')[-1]
                                        url = f"{base_url}/api/v1/artifacts/{filename}"
                                    links.append((name, url))
                except (json.JSONDecodeError, Exception):
                    pass

        result_parts = []
        if lines:
            result_parts.append("\n".join(lines))
        if links:
            link_lines = ["\n**相关链接**:"]
            for name, url in links[:5]:  # Limit to 5 links
                link_lines.append(f"• [{name}]({url})")
            result_parts.append("\n".join(link_lines))

        return "\n".join(result_parts) if result_parts else None

    async def _get_orchestrator_agent_id(self) -> UUID | None:
        """Get the ID of the RIQI Orchestrator agent."""
        if self._orchestrator_agent_id is not None:
            return self._orchestrator_agent_id

        from app.models.agents import Agent
        result = await self.session.exec(
            select(Agent).where(Agent.name == "RIQI Orchestrator")
        )
        agent = result.first()
        if agent:
            self._orchestrator_agent_id = agent.id
        return self._orchestrator_agent_id

    async def create_mission(
        self,
        *,
        task_id: UUID,
        board_id: UUID,
        goal: str,
        agent_id: UUID | None = None,
        constraints: dict[str, Any] | None = None,
        context_refs: list[str] | None = None,
        approval_policy: str = "auto",
        max_retries: int = 3,
    ) -> Mission:
        """Create a new Mission from a Task."""
        board = await Board.objects.by_id(board_id).first(self.session)
        task = await Task.objects.by_id(task_id).first(self.session)
        resolved_goal = goal
        resolved_constraints = constraints
        resolved_policy = approval_policy
        if task is not None:
            resolved_goal = goal or self.goal_builder.build(task=task, board=board)
            if resolved_constraints is None:
                resolved_constraints = self.constraint_resolver.resolve(board=board)
            policy_decision = await self.approval_gate.resolve_policy(
                board=board,
                task=task,
                requested_policy=approval_policy,
            )
            resolved_policy = policy_decision.policy

        mission = Mission(
            task_id=task_id,
            board_id=board_id,
            agent_id=agent_id,
            goal=resolved_goal,
            constraints=resolved_constraints,
            context_refs=context_refs,
            approval_policy=resolved_policy,
            max_retries=max_retries,
            status="pending",
        )
        self.session.add(mission)
        await self.session.flush()

        record_activity(
            self.session,
            event_type="mission_created",
            message=f"Mission created: {goal[:80]}",
            task_id=task_id,
            board_id=board_id,
            agent_id=agent_id,
        )
        record_activity(
            self.session,
            event_type="task.comment",
            message=f"🚀 智能体已启动分析任务。目标：{goal[:100]}",
            task_id=task_id,
            board_id=board_id,
            agent_id=agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
        await self._notify_mission_event(mission, "mission_created", "Mission created")
        return mission

    async def dispatch_mission(self, mission_id: UUID) -> Mission:
        """Dispatch a mission for execution (simulate OpenClaw handoff)."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        if mission.status not in (MISSION_STATUS_PENDING, MISSION_STATUS_FAILED):
            raise ValueError(f"Cannot dispatch mission in status '{mission.status}'")

        if mission.approval_policy == "pre_approve":
            ensure_mission_transition(mission.status, MISSION_STATUS_PENDING_APPROVAL)
            mission.status = MISSION_STATUS_PENDING_APPROVAL
            mission.updated_at = utcnow()
            self.session.add(mission)
            record_activity(
                self.session,
                event_type="approval_requested",
                message="Mission requires approval before dispatch",
                task_id=mission.task_id,
                board_id=mission.board_id,
                agent_id=mission.agent_id,
            )
            await self.session.commit()
            await self.session.refresh(mission)
            await self._notify_mission_event(
                mission,
                "approval_requested",
                "Mission requires approval before dispatch",
            )
            return mission

        ensure_mission_transition(mission.status, MISSION_STATUS_DISPATCHED)
        mission.status = MISSION_STATUS_DISPATCHED
        mission.dispatched_at = utcnow()
        mission.updated_at = utcnow()
        self.session.add(mission)

        await self._ensure_subtasks_for_mission(mission)
        await SubagentDispatchService(self.session).dispatch_subtasks_for_mission(mission)

        # Update associated task status
        task = await Task.objects.by_id(mission.task_id).first(self.session)
        if task:
            # 无论之前状态如何，派发 Mission 后 Task 必须处于 in_progress 状态
            task.status = "in_progress"
            # 核心修正：确保 Task 的委派人始终与 Mission 的执行 Agent 对齐，
            # 解决打回后委派人滞留在 Lead ID 的问题。
            if mission.agent_id:
                task.assigned_agent_id = mission.agent_id
            
            if not task.in_progress_at:
                task.in_progress_at = utcnow()
            task.updated_at = utcnow()
            self.session.add(task)

        record_activity(
            self.session,
            event_type="mission_dispatched",
            message="Mission dispatched for execution",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
        await self._notify_mission_event(mission, "mission_dispatched", "Mission dispatched")
        return mission

    async def _ensure_subtasks_for_mission(self, mission: Mission) -> None:
        existing_stmt = (
            select(MissionSubtask)
            .where(MissionSubtask.mission_id == mission.id)
            .order_by(MissionSubtask.order)
        )
        existing = list((await self.session.exec(existing_stmt)).all())
        if existing:
            return
        context = await self.context_loader.load(mission.context_refs)
        subtasks = await self.decomposer.decompose(mission=mission, context=context)
        for spec in subtasks:
            self.session.add(
                MissionSubtask(
                    mission_id=mission.id,
                    label=spec.label,
                    description=spec.description,
                    tool_scope=spec.tool_scope,
                    expected_output=spec.expected_output,
                    order=spec.order,
                    status=SUBTASK_STATUS_PENDING,
                )
            )

    async def _ensure_pending_approval(
        self,
        *,
        mission: Mission,
        aggregated: Any,
    ) -> Approval:
        if mission.approval_id:
            existing = await Approval.objects.by_id(mission.approval_id).first(self.session)
            if existing is not None and existing.status == "pending":
                return existing

        existing_stmt = (
            select(Approval)
            .where(Approval.board_id == mission.board_id)
            .where(Approval.task_id == mission.task_id)
            .where(Approval.action_type == "mission_result_review")
            .where(Approval.status == "pending")
            .order_by(Approval.created_at.desc())  # type: ignore[attr-defined]
        )
        existing = (await self.session.exec(existing_stmt)).first()
        if existing is not None:
            mission.approval_id = existing.id
            self.session.add(mission)
            return existing

        # 查找看板的 Lead Agent 角色作为审批人
        from app.models.agents import Agent
        lead_stmt = select(Agent).where(Agent.board_id == mission.board_id, Agent.is_board_lead == True)
        lead_agent = (await self.session.exec(lead_stmt)).first()
        
        approval = Approval(
            board_id=mission.board_id,
            task_id=mission.task_id,
            agent_id=lead_agent.id if lead_agent else None,
            action_type="mission_result_review",
            payload={
                "mission_id": str(mission.id),
                "summary": mission.result_summary,
                "risk": mission.result_risk,
                "next_action": mission.result_next_action,
                "anomalies": aggregated.anomalies,
            },
            confidence=0.5,
            rubric_scores={"risk": 1 if mission.result_risk == "high" else 3},
            status="pending",
        )
        self.session.add(approval)
        await self.session.flush()
        mission.approval_id = approval.id
        self.session.add(mission)
        return approval

    async def start_mission(self, mission_id: UUID) -> Mission:
        """Mark a mission as started (by execution engine)."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        mission = await self.status_tracker.update_status(
            mission_id=mission_id,
            status="running",
            message="Mission execution started",
        )
        await self._notify_mission_event(mission, "mission_started", "Mission execution started")
        return mission

    async def complete_mission(
        self,
        mission_id: UUID,
        *,
        result_summary: str | None = None,
        result_evidence: dict[str, Any] | None = None,
        result_risk: str | None = None,
        result_next_action: str | None = None,
    ) -> Mission:
        """Mark a mission as completed with results."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        subtask_rows = list(
            (
                await self.session.exec(
                    select(MissionSubtask)
                    .where(MissionSubtask.mission_id == mission.id)
                    .order_by(MissionSubtask.order),
                )
            ).all()
        )
        subtask_results: list[dict[str, Any]] = [
            {
                "label": row.label,
                "status": row.status,
                "result_summary": row.result_summary,
                "result_risk": row.result_risk,
                "error_message": row.error_message,
                "expected_output": row.expected_output,
            }
            for row in subtask_rows
        ]
        aggregated = await self.aggregator.aggregate(
            mission=mission, subtask_results=subtask_results
        )

        # Get task title for Lead Auditor
        task_title = None
        if mission.task_id:
            from app.models.tasks import Task

            task = await Task.objects.by_id(mission.task_id).first(self.session)
            if task:
                task_title = task.title

        approval_decision = await self.approval_gate.evaluate_result(
            mission=mission, aggregated=aggregated, task_title=task_title
        )

        ensure_mission_transition(mission.status, approval_decision.status)
        mission.status = approval_decision.status
        mission.completed_at = utcnow()
        mission.result_summary = result_summary or aggregated.summary
        mission.result_evidence = result_evidence or aggregated.evidence
        mission.result_risk = result_risk or aggregated.risk
        mission.result_next_action = result_next_action or aggregated.next_action
        mission.updated_at = utcnow()
        self.session.add(mission)
        approval_requested = False
        if mission.status == MISSION_STATUS_PENDING_APPROVAL:
            await self._ensure_pending_approval(mission=mission, aggregated=aggregated)
            approval_requested = True

        # Update related task with results
        task = await Task.objects.by_id(mission.task_id).first(self.session)
        if task:
            # If auto-approval is enabled and mission completed successfully, skip review and mark as done.
            # Otherwise move to review for human/lead intervention.
            from app.services.missions.status_machine import MISSION_STATUS_COMPLETED

            if (
                mission.approval_policy == "auto"
                and mission.status == MISSION_STATUS_COMPLETED
            ):
                task.status = "done"
            else:
                task.status = "review"

            task.result_summary = mission.result_summary
            task.result_risk = mission.result_risk
            task.result_next_action = mission.result_next_action
            task.updated_at = utcnow()

            # Assign task to lead agent for review
            if task.board_id is not None:
                lead_result = await self.session.exec(
                    select(Agent)
                    .where(Agent.board_id == task.board_id)
                    .where(Agent.is_board_lead == True)
                )
                lead = lead_result.first()
                if lead:
                    task.assigned_agent_id = lead.id

            self.session.add(task)

        record_activity(
            self.session,
            event_type="mission_completed",
            message=(
                f"Mission completed ({mission.status}): "
                f"{mission.result_summary[:80] if mission.result_summary else 'No summary'}"
            ),
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )
        # 确定评论执行者标识
        effective_agent_id = mission.agent_id or (task.assigned_agent_id if task else None)

        # 调用 Lead Agent 生成智能评论
        lead_comment = await self._generate_lead_comment(mission, task)

        record_activity(
            self.session,
            event_type="task.comment",
            message=lead_comment,
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=effective_agent_id,
        )

        # 只要任务进入 review 状态，无论是否显式请求审批记录，都发表 Lead 确认评论
        if (task and task.status == "review") or approval_requested:
            if approval_requested:
                record_activity(
                    self.session,
                    event_type="approval_requested",
                    message="Approval requested for mission result review",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=effective_agent_id,
                )

            # 增加 Lead 的确认评论署名
            lead_stmt = select(Agent).where(Agent.board_id == mission.board_id, Agent.is_board_lead == True)
            lead_agent = (await self.session.exec(lead_stmt)).first()
            if lead_agent:
                record_activity(
                    self.session,
                    event_type="task.comment",
                    message="👀 我已收到本轮工作的成果提交，正在评估逻辑并对比目标达成度，请稍后。",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=lead_agent.id,
                )

                # Dispatch audit request to Lead Agent via Gateway
                if mission.approval_policy == "post_review" and lead_agent.openclaw_session_id:
                    from app.services.openclaw.lead_auditor import LeadAuditDispatcher

                    board = await Board.objects.by_id(mission.board_id).first(self.session)
                    if board:
                        callback_url = f"{settings.base_url}/api/v1/missions/{mission.id}/audit"
                        dispatcher = LeadAuditDispatcher(self.session)
                        await dispatcher.dispatch_audit(
                            mission=mission,
                            task_title=task_title or "Unknown Task",
                            board=board,
                            lead=lead_agent,
                            aggregated=aggregated,
                            callback_url=callback_url,
                        )

        await self.session.commit()
        await self.session.refresh(mission)
        if task and task.external_source == "feishu" and mission.status == MISSION_STATUS_COMPLETED:
            config = (
                await FeishuSyncConfig.objects.filter_by(board_id=mission.board_id, enabled=True)
                .order_by(FeishuSyncConfig.updated_at.desc())
                .first(self.session)
            )
            if config is not None:
                await WritebackService(self.session, config).push_task_result(task.id)
        if approval_requested:
            await self._notify_mission_event(
                mission,
                "approval_requested",
                "Mission requires human approval before finalization",
            )
        else:
            # Get the Execute subtask result as the main output
            result_output = await self._get_execute_result(mission.id)
            notify_message = result_output if result_output else "Mission completed"

            logger.info("complete_mission.notifying mission_id=%s message=%s", mission.id, notify_message[:50])
            await self._notify_mission_event(
                mission,
                "mission_completed",
                notify_message,
            )
        return mission

    async def _generate_lead_comment(
        self,
        mission: Mission,
        task: Task | None,
    ) -> str:
        """Generate intelligent comment using Lead Agent.

        Falls back to template if Lead Agent is not available.
        """
        try:
            # Find Lead Agent
            lead_stmt = select(Agent).where(
                Agent.board_id == mission.board_id,
                Agent.is_board_lead == True  # noqa: E712
            )
            lead_agent = (await self.session.exec(lead_stmt)).first()

            if not lead_agent or not lead_agent.openclaw_session_id:
                # Fallback to template
                return self._get_fallback_comment(mission)

            # Get task title
            task_title = task.title if task else "Unknown Task"

            # Extract subtask results from result_evidence
            subtask_results = []
            if mission.result_evidence:
                evidence = mission.result_evidence
                if isinstance(evidence, dict):
                    subtask_results = evidence.get("subtask_results", [])

            # Build the instruction for Lead Agent
            from jinja2 import Environment, FileSystemLoader
            from pathlib import Path

            templates_root = Path(__file__).resolve().parents[3] / "templates"
            env = Environment(
                loader=FileSystemLoader(templates_root),
                autoescape=False,
            )

            template = env.get_template("lead_comment.md.j2")
            instruction = template.render(
                task_title=task_title,
                mission_goal=mission.goal or "",
                result_summary=mission.result_summary or "",
                result_risk=mission.result_risk or "unknown",
                next_action=mission.result_next_action or "",
                subtask_results=subtask_results,
            )

            # Call Lead Agent via Gateway
            from app.services.openclaw.gateway_rpc import ensure_session, send_message, get_chat_history
            from app.services.openclaw.gateway_resolver import gateway_client_config, get_gateway_for_board
            from app.models.boards import Board

            board = await Board.objects.by_id(mission.board_id).first(self.session)
            if not board:
                logger.warning("lead_comment.no_board board_id=%s", mission.board_id)
                return self._get_fallback_comment(mission)

            gateway = await get_gateway_for_board(self.session, board)
            if not gateway:
                logger.warning("lead_comment.no_gateway board_id=%s", mission.board_id)
                return self._get_fallback_comment(mission)

            config = gateway_client_config(gateway)
            session_key = lead_agent.openclaw_session_id

            logger.info("lead_comment.calling agent=%s session=%s", lead_agent.name, session_key)

            # Ensure session exists
            await ensure_session(session_key, config=config, label=lead_agent.name)

            # Send message to Lead Agent (starts the task)
            await send_message(
                instruction,
                session_key=session_key,
                config=config,
                deliver=True,
            )

            # Wait for Lead Agent to process and respond
            import asyncio
            await asyncio.sleep(5)

            # Get chat history to extract Lead Agent's response
            history = await get_chat_history(session_key, config=config, limit=3)

            # Extract comment from chat history
            if history and isinstance(history, dict):
                messages = history.get("messages", [])
                # Find the latest assistant message with the generated comment
                for msg in reversed(messages):
                    if msg.get("role") == "assistant":
                        content_list = msg.get("content", [])
                        for item in content_list:
                            if item.get("type") == "text":
                                comment = item.get("text", "").strip()
                                # Filter out NO_REPLY markers and system messages
                                if comment and len(comment) > 10 and "NO_REPLY" not in comment and "Take action" not in comment:
                                    logger.info("lead_comment.generated agent=%s length=%d", lead_agent.name, len(comment))
                                    return comment

            # If we get here, result was empty or invalid
            logger.warning("lead_comment.empty_response falling_back")

        except Exception as e:
            logger.warning("lead_comment.exception error=%s", str(e)[:200])

        # Fallback to template
        fallback = self._get_fallback_comment(mission)
        logger.info("lead_comment.using_fallback mission_id=%s fallback=%s", mission.id, fallback[:50])
        return fallback

    async def _get_execute_result(self, mission_id: UUID) -> str | None:
        """Get the Execute subtask result for notification."""
        from app.models.missions import MissionSubtask

        result = await self.session.exec(
            select(MissionSubtask)
            .where(MissionSubtask.mission_id == mission_id)
            .where(MissionSubtask.label == "Execute")
        )
        execute_subtask = result.first()
        if not execute_subtask:
            return None

        # First try result_evidence for actual output content
        if execute_subtask.result_evidence:
            evidence = execute_subtask.result_evidence
            if isinstance(evidence, dict):
                output = evidence.get("output")
                if output:
                    return str(output)[:1000]

        # Fall back to result_summary
        if execute_subtask.result_summary:
            return execute_subtask.result_summary[:500]
        return None

    def _get_fallback_comment(self, mission: Mission) -> str:
        """Generate a fallback comment using template."""
        return f"🏁 任务已完成。汇总结果：{mission.result_summary[:150] if mission.result_summary else '已就绪'}"

    async def fail_mission(
        self,
        mission_id: UUID,
        *,
        error_message: str,
    ) -> Mission:
        """Mark a mission as failed."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        ensure_mission_transition(mission.status, MISSION_STATUS_FAILED)
        mission.status = MISSION_STATUS_FAILED
        mission.error_message = error_message
        mission.retry_count += 1
        mission.updated_at = utcnow()
        self.session.add(mission)

        record_activity(
            self.session,
            event_type="mission_failed",
            message=f"Mission failed: {error_message[:80]}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
        await self._notify_mission_event(
            mission, "mission_failed", f"Mission failed: {error_message[:120]}"
        )
        return mission

    async def cancel_mission(self, mission_id: UUID) -> Mission:
        """Cancel a pending or running mission."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        if mission.status in (MISSION_STATUS_COMPLETED, MISSION_STATUS_CANCELLED):
            raise ValueError(f"Cannot cancel mission in status '{mission.status}'")

        ensure_mission_transition(mission.status, MISSION_STATUS_CANCELLED)
        mission.status = MISSION_STATUS_CANCELLED
        mission.updated_at = utcnow()
        self.session.add(mission)

        record_activity(
            self.session,
            event_type="mission_cancelled",
            message="Mission cancelled",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
        await self._notify_mission_event(mission, "mission_cancelled", "Mission cancelled")
        return mission

    async def create_subtask(
        self,
        *,
        mission_id: UUID,
        label: str,
        description: str | None = None,
        tool_scope: list[str] | None = None,
        expected_output: str | None = None,
        order: int = 0,
    ) -> MissionSubtask:
        """Create a subtask for a mission."""
        subtask = MissionSubtask(
            mission_id=mission_id,
            label=label,
            description=description,
            tool_scope=tool_scope,
            expected_output=expected_output,
            order=order,
        )
        self.session.add(subtask)
        await self.session.flush()

        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission:
            record_activity(
                self.session,
                event_type="subtask_created",
                message=f"Subtask created: {label}",
                task_id=mission.task_id,
                board_id=mission.board_id,
                agent_id=mission.agent_id,
            )

        await self.session.commit()
        await self.session.refresh(subtask)
        return subtask

    async def _all_subtasks_terminal(self, mission_id: UUID) -> bool:
        rows = list(
            (
                await self.session.exec(
                    select(MissionSubtask)
                    .where(MissionSubtask.mission_id == mission_id)
                    .order_by(MissionSubtask.order),
                )
            ).all()
        )
        if not rows:
            return False
        return all(row.status in SUBTASK_TERMINAL_STATUSES for row in rows)

    async def update_subtask_status(
        self,
        subtask_id: UUID,
        *,
        status: str,
        result_summary: str | None = None,
        result_evidence: dict[str, Any] | None = None,
        result_risk: str | None = None,
        error_message: str | None = None,
    ) -> MissionSubtask:
        """Update the status and result of a subtask."""
        subtask = await MissionSubtask.objects.by_id(subtask_id).first(self.session)
        if subtask is None:
            raise ValueError(f"Subtask {subtask_id} not found")
        mission = await Mission.objects.by_id(subtask.mission_id).first(self.session)

        ensure_subtask_transition(subtask.status, status)
        subtask.status = status
        if status == SUBTASK_STATUS_RUNNING:
            subtask.started_at = utcnow()
        elif status in (SUBTASK_STATUS_COMPLETED, SUBTASK_STATUS_FAILED):
            subtask.completed_at = utcnow()

        if result_summary is not None:
            subtask.result_summary = result_summary
        if result_evidence is not None:
            subtask.result_evidence = result_evidence
        if result_risk is not None:
            subtask.result_risk = result_risk
        if error_message is not None:
            subtask.error_message = error_message
        subtask.updated_at = utcnow()
        self.session.add(subtask)

        if mission is not None:
            orch_agent_id = await self._get_orchestrator_agent_id()
            if status == SUBTASK_STATUS_RUNNING:
                record_activity(
                    self.session,
                    event_type="subtask_started",
                    message=f"Subtask started: {subtask.label}",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=mission.agent_id,
                )
                record_activity(
                    self.session,
                    event_type="task.comment",
                    message=f"[执行者: 智能体 {subtask.order + 1}] 🛠️ 正在执行阶段：{subtask.label}",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=orch_agent_id,
                )
            elif status == SUBTASK_STATUS_COMPLETED:
                record_activity(
                    self.session,
                    event_type="subtask_completed",
                    message=f"Subtask completed: {subtask.label}",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=mission.agent_id,
                )
                record_activity(
                    self.session,
                    event_type="task.comment",
                    message=f"[执行者: 智能体 {subtask.order + 1}] ✅ 阶段性结果已达成 [{subtask.label}]：{subtask.result_summary or '已完成分析'}",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=orch_agent_id,
                )
            elif status == SUBTASK_STATUS_FAILED:
                record_activity(
                    self.session,
                    event_type="subtask_failed",
                    message=f"Subtask failed: {subtask.label}",
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=mission.agent_id,
                )

        await self.session.commit()
        await self.session.refresh(subtask)

        if (
            mission is not None
            and mission.status in {MISSION_STATUS_DISPATCHED, MISSION_STATUS_RUNNING}
            and status in {SUBTASK_STATUS_COMPLETED, SUBTASK_STATUS_FAILED}
            and await self._all_subtasks_terminal(mission.id)
        ):
            ensure_mission_transition(mission.status, MISSION_STATUS_AGGREGATING)
            mission.status = MISSION_STATUS_AGGREGATING
            mission.updated_at = utcnow()
            self.session.add(mission)
            await self.session.commit()
            await self.complete_mission(mission.id)
        return subtask

    async def get_mission_subtasks(self, mission_id: UUID) -> list[MissionSubtask]:
        """Retrieve all subtasks for a mission, ordered by `order`."""
        stmt = (
            select(MissionSubtask)
            .where(MissionSubtask.mission_id == mission_id)
            .order_by(MissionSubtask.order)
        )
        result = await self.session.exec(stmt)
        return list(result.all())

    async def redispatch_subtask(self, subtask_id: UUID) -> MissionSubtask:
        """Reset and redispatch a subtask into its dedicated session."""
        subtask = await MissionSubtask.objects.by_id(subtask_id).first(self.session)
        if subtask is None:
            raise ValueError(f"Subtask {subtask_id} not found")
        mission = await Mission.objects.by_id(subtask.mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {subtask.mission_id} not found")

        ensure_subtask_transition(subtask.status, SUBTASK_STATUS_PENDING)
        subtask.status = SUBTASK_STATUS_PENDING
        subtask.result_summary = None
        subtask.result_evidence = None
        subtask.result_risk = None
        subtask.error_message = None
        subtask.started_at = None
        subtask.completed_at = None
        subtask.updated_at = utcnow()
        self.session.add(subtask)

        ensure_mission_transition(mission.status, MISSION_STATUS_RUNNING)
        mission.status = MISSION_STATUS_RUNNING
        mission.completed_at = None
        mission.error_message = None
        mission.updated_at = utcnow()
        self.session.add(mission)

        record_activity(
            self.session,
            event_type="subtask_redispatched",
            message=f"Subtask redispatched: {subtask.label}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await SubagentDispatchService(self.session).dispatch_subtask(mission, subtask)
        await self.session.commit()
        await self.session.refresh(subtask)
        return subtask

    async def handle_lead_audit(
        self,
        mission_id: UUID,
        decision: str,
        summary: str | None = None,
        reason: str | None = None,
        suggestions: list[str] | None = None,
    ) -> Mission:
        """Handle Lead Agent audit callback."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        # Check if mission is in correct state for audit
        # Accept both pending_approval (normal flow) and failed/completed (test/retry)
        if mission.status not in (
            MISSION_STATUS_PENDING_APPROVAL,
            MISSION_STATUS_FAILED,
            MISSION_STATUS_COMPLETED,
        ):
            raise ValueError(
                f"Mission {mission_id} cannot receive audit in status '{mission.status}'"
            )

        # Normalise: treat failed/completed missions as pending_approval for audit purposes
        if mission.status != MISSION_STATUS_PENDING_APPROVAL:
            mission.status = MISSION_STATUS_PENDING_APPROVAL
            mission.updated_at = utcnow()
            self.session.add(mission)

        # Record audit decision as comment on the task
        if mission.task_id:
            from app.models.tasks import Task

            task = await Task.objects.by_id(mission.task_id).first(self.session)
            if task:
                # Find the lead agent for comment attribution
                lead_agent = None
                if mission.board_id:
                    from app.models.agents import Agent
                    from sqlmodel import select

                    stmt = select(Agent).where(
                        Agent.board_id == mission.board_id,
                        Agent.is_board_lead == True,  # noqa: E712
                    )
                    lead_agent = (await self.session.exec(stmt)).first()

                comment_message = f"[Lead Agent Audit]"
                if decision == "approve":
                    comment_message += f"\n\n✅ Decision: Approved\n\n{summary or ''}"
                else:
                    comment_message += f"\n\n❌ Decision: Changes Requested\n\n{reason or ''}"
                    if suggestions:
                        comment_message += "\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions)

                record_activity(
                    self.session,
                    event_type="task.comment",
                    message=comment_message,
                    task_id=mission.task_id,
                    board_id=mission.board_id,
                    agent_id=lead_agent.id if lead_agent else None,
                )

        # Update mission based on decision
        if decision == "approve":
            ensure_mission_transition(mission.status, MISSION_STATUS_COMPLETED)
            mission.status = MISSION_STATUS_COMPLETED
            mission.completed_at = utcnow()
            record_activity(
                self.session,
                event_type="mission_approved",
                message=f"Mission approved by Lead Agent: {summary or ''}",
                task_id=mission.task_id,
                board_id=mission.board_id,
                agent_id=mission.agent_id,
            )
        else:
            # Changes requested - move back to running for revision
            ensure_mission_transition(mission.status, MISSION_STATUS_RUNNING)
            mission.status = MISSION_STATUS_RUNNING
            mission.error_message = reason

            # Also update the task status to in_progress for rework
            if mission.task_id:
                task = await Task.objects.by_id(mission.task_id).first(self.session)
                if task:
                    task.status = "in_progress"
                    self.session.add(task)

            record_activity(
                self.session,
                event_type="mission_rejected",
                message=f"Mission returned for revisions: {reason or ''}",
                task_id=mission.task_id,
                board_id=mission.board_id,
                agent_id=mission.agent_id,
            )

        mission.updated_at = utcnow()
        self.session.add(mission)
        await self.session.commit()
        await self.session.refresh(mission)
        return mission
