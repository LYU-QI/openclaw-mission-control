"""Periodic timeout handling for mission subtasks."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.missions import MissionSubtask
from app.services.missions.orchestrator import MissionOrchestrator


def _timeout_cutoff():
    minutes = max(int(settings.mission_subtask_timeout_minutes), 1)
    return utcnow() - timedelta(minutes=minutes)


async def fail_timed_out_subtasks(session: AsyncSession) -> int:
    """Fail pending/running subtasks that exceeded the configured timeout window."""
    cutoff = _timeout_cutoff()
    stmt = (
        select(MissionSubtask)
        .where(MissionSubtask.status.in_(("pending", "running")))
        .where(MissionSubtask.assigned_subagent_id.is_not(None))
        .where(MissionSubtask.updated_at <= cutoff)
        .order_by(MissionSubtask.updated_at.asc())
    )
    rows = list((await session.exec(stmt)).all())
    if not rows:
        return 0

    orchestrator = MissionOrchestrator(session)
    count = 0
    for subtask in rows:
        await orchestrator.update_subtask_status(
            subtask.id,
            status="failed",
            error_message="Subtask timed out waiting for callback.",
            result_risk="high",
        )
        count += 1
    return count
