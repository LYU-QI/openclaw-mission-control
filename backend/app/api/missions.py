"""Mission CRUD, dispatch, and lifecycle API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import AUTH_DEP, SESSION_DEP
from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.missions import Mission, MissionSubtask
from app.schemas.missions import (
    LeadAuditCallback,
    MissionCreate,
    MissionDispatchRequest,
    MissionRead,
    MissionTimelineEntry,
    MissionUpdate,
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
)
from app.services.missions.orchestrator import MissionOrchestrator
from app.services.missions.status_machine import (
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_FAILED,
    MISSION_STATUS_PENDING,
    MISSION_STATUS_PENDING_APPROVAL,
    ensure_mission_transition,
)
from app.services.missions.timeline import timeline_meta_for_event

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

router = APIRouter(prefix="/missions", tags=["missions", "agent-orchestrator"])


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
    payload: MissionDispatchRequest | None = None,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Dispatch a mission to the OpenClaw execution engine."""
    _ = payload
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


@router.get("/{mission_id}/timeline", response_model=list[MissionTimelineEntry])
async def mission_timeline(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[MissionTimelineEntry]:
    """Return a mission execution timeline built from activity events."""
    mission = await Mission.objects.by_id(mission_id).first(session)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    stmt = (
        select(ActivityEvent)
        .where(ActivityEvent.board_id == mission.board_id)
        .where(ActivityEvent.task_id == mission.task_id)
        .where(
            ActivityEvent.event_type.in_(
                [
                    "mission_created",
                    "mission_dispatched",
                    "mission_started",
                    "mission_completed",
                    "mission_failed",
                    "mission_cancelled",
                    "subtask_created",
                    "subtask_started",
                    "subtask_completed",
                    "subtask_failed",
                    "approval_requested",
                    "approval_granted",
                    "approval_rejected",
                ],
            ),
        )
        .order_by(ActivityEvent.created_at.asc())  # type: ignore[attr-defined]
    )
    events = list((await session.exec(stmt)).all())
    return [
        MissionTimelineEntry(
            timestamp=event.created_at,
            event_type=event.event_type,
            stage=str(timeline_meta_for_event(event.event_type)["stage"]),
            stage_label=str(timeline_meta_for_event(event.event_type)["stage_label"]),
            tone=str(timeline_meta_for_event(event.event_type)["tone"]),
            status_hint=timeline_meta_for_event(event.event_type)["status_hint"],
            message=event.message,
            agent_id=event.agent_id,
        )
        for event in events
    ]


@router.post("/{mission_id}/approve", response_model=MissionRead)
async def approve_mission(
    mission_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Approve a mission waiting for pre-approval and continue dispatch."""
    mission = await Mission.objects.by_id(mission_id).first(session)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if mission.status != MISSION_STATUS_PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission is not in pending_approval state",
        )
    ensure_mission_transition(mission.status, MISSION_STATUS_PENDING)
    mission.status = MISSION_STATUS_PENDING
    if mission.approval_policy == "pre_approve":
        mission.approval_policy = "auto"
    mission.updated_at = utcnow()
    session.add(mission)
    await session.commit()
    orchestrator = MissionOrchestrator(session)
    return await orchestrator.dispatch_mission(mission_id)


@router.post("/{mission_id}/review", response_model=MissionRead)
async def review_mission(
    mission_id: UUID,
    payload: MissionUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> Mission:
    """Review a post-review mission and finalize as completed/failed."""
    mission = await Mission.objects.by_id(mission_id).first(session)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if mission.status not in {
        MISSION_STATUS_PENDING_APPROVAL,
        MISSION_STATUS_COMPLETED,
        MISSION_STATUS_FAILED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mission is not ready for review",
        )

    if payload.status == MISSION_STATUS_FAILED:
        ensure_mission_transition(mission.status, MISSION_STATUS_FAILED)
        mission.status = MISSION_STATUS_FAILED
        mission.error_message = payload.error_message or mission.error_message
    else:
        ensure_mission_transition(mission.status, MISSION_STATUS_COMPLETED)
        mission.status = MISSION_STATUS_COMPLETED
        mission.result_summary = payload.result_summary or mission.result_summary
        mission.result_evidence = payload.result_evidence or mission.result_evidence
        mission.result_risk = payload.result_risk or mission.result_risk
        mission.result_next_action = payload.result_next_action or mission.result_next_action
        mission.completed_at = mission.completed_at or utcnow()
    mission.updated_at = utcnow()
    session.add(mission)
    await session.commit()
    await session.refresh(mission)
    return mission


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


@router.post("/subtasks/{subtask_id}/redispatch", response_model=SubtaskRead)
async def redispatch_subtask(
    subtask_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> MissionSubtask:
    """Reset and redispatch a subtask into its dedicated OpenClaw session."""
    orchestrator = MissionOrchestrator(session)
    try:
        return await orchestrator.redispatch_subtask(subtask_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{mission_id}/audit", tags=["missions", "agent-orchestrator", "agent-lead"])
async def lead_audit_callback(
    mission_id: UUID,
    payload: LeadAuditCallback,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> dict[str, str]:
    """Callback endpoint for Lead Agent audit results."""
    from app.services.missions.orchestrator import MissionOrchestrator

    orchestrator = MissionOrchestrator(session)
    try:
        await orchestrator.handle_lead_audit(
            mission_id=mission_id,
            decision=payload.decision,
            summary=payload.summary,
            reason=payload.reason,
            suggestions=payload.suggestions or [],
        )
        return {"status": "ok", "message": f"Mission {mission_id} audit processed"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
