"""Mission status tracking with mirrored task state updates."""

from __future__ import annotations

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.missions import Mission
from app.models.tasks import Task
from app.services.activity_log import record_activity


class MissionStatusTracker:
    """Centralized mission status transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def update_status(self, *, mission_id: UUID, status: str, message: str | None = None) -> Mission:
        mission = await Mission.objects.by_id(mission_id).first(self.session)
        if mission is None:
            raise ValueError(f"Mission {mission_id} not found")

        mission.status = status
        mission.updated_at = utcnow()
        if status == "running":
            mission.started_at = mission.started_at or utcnow()
        if status in {"completed", "failed"}:
            mission.completed_at = mission.completed_at or utcnow()
        self.session.add(mission)

        task = await Task.objects.by_id(mission.task_id).first(self.session)
        if task:
            if status == "running":
                task.status = "in_progress"
                task.in_progress_at = task.in_progress_at or utcnow()
            elif status == "completed":
                task.status = "review"
            elif status == "failed":
                task.status = "inbox"
                task.assigned_agent_id = None
            task.updated_at = utcnow()
            self.session.add(task)

        record_activity(
            self.session,
            event_type=f"mission_{status}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
            message=message,
        )
        await self.session.commit()
        await self.session.refresh(mission)
        return mission

