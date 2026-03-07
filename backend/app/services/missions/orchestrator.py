"""Mission lifecycle orchestration and status tracking."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.missions import Mission, MissionSubtask
from app.models.tasks import Task
from app.services.activity_log import record_activity

logger = logging.getLogger(__name__)


class MissionOrchestrator:
    """Creates, dispatches, and manages the lifecycle of Missions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

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
        mission = Mission(
            task_id=task_id,
            board_id=board_id,
            agent_id=agent_id,
            goal=goal,
            constraints=constraints,
            context_refs=context_refs,
            approval_policy=approval_policy,
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

        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def dispatch_mission(self, mission_id: UUID) -> Mission:
        """Dispatch a mission for execution (simulate OpenClaw handoff)."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        if mission.status not in ("pending", "failed"):
            raise ValueError(f"Cannot dispatch mission in status '{mission.status}'")

        mission.status = "dispatched"
        mission.dispatched_at = utcnow()
        mission.updated_at = utcnow()
        self.session.add(mission)

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
            message=f"Mission dispatched for execution",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
        return mission

    async def start_mission(self, mission_id: UUID) -> Mission:
        """Mark a mission as started (by execution engine)."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        mission.status = "running"
        mission.started_at = utcnow()
        mission.updated_at = utcnow()
        self.session.add(mission)

        record_activity(
            self.session,
            event_type="mission_started",
            message="Mission execution started",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
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

        mission.status = "completed"
        mission.completed_at = utcnow()
        mission.result_summary = result_summary
        mission.result_evidence = result_evidence
        mission.result_risk = result_risk
        mission.result_next_action = result_next_action
        mission.updated_at = utcnow()
        self.session.add(mission)

        # Update related task with results
        task = await Task.objects.by_id(mission.task_id).first(self.session)
        if task:
            task.status = "review"
            task.result_summary = result_summary
            task.result_risk = result_risk
            task.result_next_action = result_next_action
            task.updated_at = utcnow()
            self.session.add(task)

        record_activity(
            self.session,
            event_type="mission_completed",
            message=f"Mission completed: {result_summary[:80] if result_summary else 'No summary'}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        await self.session.commit()
        await self.session.refresh(mission)
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

        mission.status = "failed"
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
        return mission

    async def cancel_mission(self, mission_id: UUID) -> Mission:
        """Cancel a pending or running mission."""
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        if mission.status in ("completed", "cancelled"):
            raise ValueError(f"Cannot cancel mission in status '{mission.status}'")

        mission.status = "cancelled"
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

        subtask.status = status
        if status == "running":
            subtask.started_at = utcnow()
        elif status in ("completed", "failed"):
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

        await self.session.commit()
        await self.session.refresh(subtask)
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
