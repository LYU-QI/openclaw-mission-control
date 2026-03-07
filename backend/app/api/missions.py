"""Mission CRUD, dispatch, and lifecycle API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.api.deps import AUTH_DEP, SESSION_DEP
from app.core.time import utcnow
from app.models.missions import Mission, MissionSubtask
from app.schemas.missions import (
    MissionCreate,
    MissionDispatchRequest,
    MissionRead,
    MissionUpdate,
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
)
from app.services.missions.orchestrator import MissionOrchestrator

if TYPE_CHECKING:
    from app.core.auth import AuthContext
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/missions", tags=["missions"])


@router.post("", response_model=MissionRead, status_code=status.HTTP_201_CREATED)
async def create_mission(
    payload: MissionCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Create a new mission from a task."""
    orchestrator = MissionOrchestrator(session)
    return await orchestrator.create_mission(
        task_id=payload.task_id,
        board_id=payload.board_id,
        agent_id=payload.agent_id,
        goal=payload.goal,
        constraints=payload.constraints,
        context_refs=payload.context_refs,
        approval_policy=payload.approval_policy,
        max_retries=payload.max_retries,
    )


@router.get("", response_model=list[MissionRead])
async def list_missions(
    board_id: UUID | None = None,
    task_id: UUID | None = None,
    mission_status: str | None = None,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[Mission]:
    """List missions, optionally filtered by board, task, or status."""
    stmt = select(Mission).order_by(Mission.created_at.desc())  # type: ignore[attr-defined]
    if board_id:
        stmt = stmt.where(Mission.board_id == board_id)
    if task_id:
        stmt = stmt.where(Mission.task_id == task_id)
    if mission_status:
        stmt = stmt.where(Mission.status == mission_status)
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Retrieve a single mission by ID."""
    mission = await Mission.objects.by_id(mission_id).first(session)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return mission


@router.patch("/{mission_id}", response_model=MissionRead)
async def update_mission(
    mission_id: UUID,
    payload: MissionUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Update a mission."""
    mission = await Mission.objects.by_id(mission_id).first(session)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mission, key, value)
    mission.updated_at = utcnow()
    session.add(mission)
    await session.commit()
    await session.refresh(mission)
    return mission


@router.post("/{mission_id}/dispatch", response_model=MissionRead)
async def dispatch_mission(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Dispatch a mission to the OpenClaw execution engine."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.dispatch_mission(mission_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/start", response_model=MissionRead)
async def start_mission(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Mark a dispatched mission as started."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.start_mission(mission_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/complete", response_model=MissionRead)
async def complete_mission(
    mission_id: UUID,
    payload: MissionUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Mark a mission as completed with results."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.complete_mission(
            mission_id,
            result_summary=payload.result_summary,
            result_evidence=payload.result_evidence,
            result_risk=payload.result_risk,
            result_next_action=payload.result_next_action,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/fail", response_model=MissionRead)
async def fail_mission(
    mission_id: UUID,
    payload: MissionUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Mark a mission as failed."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.fail_mission(
            mission_id,
            error_message=payload.error_message or "Unknown error",
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{mission_id}/cancel", response_model=MissionRead)
async def cancel_mission(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Cancel a pending or running mission."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.cancel_mission(mission_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ------------------------------------------------------------------
# Subtask endpoints
# ------------------------------------------------------------------


@router.get("/{mission_id}/subtasks", response_model=list[SubtaskRead])
async def list_subtasks(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[MissionSubtask]:
    """List all subtasks for a mission."""
    orchestrator = MissionOrchestrator(session)
    return await orchestrator.get_mission_subtasks(mission_id)


@router.post(
    "/{mission_id}/subtasks",
    response_model=SubtaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtask(
    mission_id: UUID,
    payload: SubtaskCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MissionSubtask:
    """Create a subtask for a mission."""
    orchestrator = MissionOrchestrator(session)
    return await orchestrator.create_subtask(
        mission_id=mission_id,
        label=payload.label,
        description=payload.description,
        tool_scope=payload.tool_scope,
        expected_output=payload.expected_output,
        order=payload.order,
    )


@router.patch("/subtasks/{subtask_id}", response_model=SubtaskRead)
async def update_subtask(
    subtask_id: UUID,
    payload: SubtaskUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MissionSubtask:
    """Update a subtask's status and result."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.update_subtask_status(
            subtask_id,
            status=payload.status or "pending",
            result_summary=payload.result_summary,
            result_evidence=payload.result_evidence,
            result_risk=payload.result_risk,
            error_message=payload.error_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
