"""Mission lifecycle orchestration and status tracking."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.approvals import Approval
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
        await self.notification_service.notify(
            organization_id=board.organization_id,
            board_id=board.id,
            event_type=event_type,
            message=message,
            extra={"mission_id": str(mission.id), "task_id": str(mission.task_id)},
        )

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
        if task and task.status == "inbox":
            task.status = "in_progress"
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

        approval = Approval(
            board_id=mission.board_id,
            task_id=mission.task_id,
            agent_id=mission.agent_id,
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
        approval_decision = await self.approval_gate.evaluate_result(
            mission=mission, aggregated=aggregated
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
            task.status = "review"
            task.result_summary = mission.result_summary
            task.result_risk = mission.result_risk
            task.result_next_action = mission.result_next_action
            task.updated_at = utcnow()
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
        record_activity(
            self.session,
            event_type="task.comment",
            message=f"🏁 任务全链路分析圆满完成。汇总结果：{mission.result_summary[:150] if mission.result_summary else '已就绪'}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )
        if approval_requested:
            record_activity(
                self.session,
                event_type="approval_requested",
                message="Approval requested for mission result review",
                task_id=mission.task_id,
                board_id=mission.board_id,
                agent_id=mission.agent_id,
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
            await self._notify_mission_event(mission, "mission_completed", "Mission completed")
        return mission

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
