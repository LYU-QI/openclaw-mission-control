"""Schemas for Mission CRUD and subtask API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlmodel import Field, SQLModel

MissionStatus = Literal[
    "pending",
    "dispatched",
    "running",
    "aggregating",
    "completed",
    "failed",
    "pending_approval",
    "cancelled",
]

ApprovalPolicy = Literal["auto", "pre_approve", "post_review"]

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class MissionCreate(SQLModel):
    """Payload for creating a mission from a task."""

    task_id: UUID
    board_id: UUID
    agent_id: UUID | None = None
    goal: str
    constraints: dict[str, Any] | None = None
    context_refs: list[str] | None = None
    approval_policy: ApprovalPolicy = "auto"
    max_retries: int = Field(default=3, ge=0, le=10)


class MissionUpdate(SQLModel):
    """Payload for updating a mission."""

    goal: str | None = None
    constraints: dict[str, Any] | None = None
    context_refs: list[str] | None = None
    approval_policy: ApprovalPolicy | None = None
    status: MissionStatus | None = None
    result_summary: str | None = None
    result_evidence: dict[str, Any] | None = None
    result_risk: str | None = None
    result_next_action: str | None = None
    error_message: str | None = None


class MissionRead(SQLModel):
    """Mission payload returned from read endpoints."""

    id: UUID
    task_id: UUID
    board_id: UUID
    agent_id: UUID | None
    goal: str
    constraints: dict[str, Any] | None
    context_refs: list[str] | None
    approval_policy: str
    approval_id: UUID | None
    status: str
    dispatched_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    result_summary: str | None
    result_evidence: dict[str, Any] | None
    result_risk: str | None
    result_next_action: str | None
    retry_count: int
    max_retries: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SubtaskCreate(SQLModel):
    """Payload for creating a mission subtask."""

    mission_id: UUID
    label: str
    description: str | None = None
    tool_scope: list[str] | None = None
    expected_output: str | None = None
    order: int = 0


class SubtaskUpdate(SQLModel):
    """Payload for updating a mission subtask."""

    status: Literal["pending", "running", "completed", "failed"] | None = None
    result_summary: str | None = None
    result_evidence: dict[str, Any] | None = None
    result_risk: str | None = None
    error_message: str | None = None
    assigned_subagent_id: str | None = None


class LeadAuditCallback(SQLModel):
    """Payload for Lead Agent audit callback."""

    status: Literal["approved", "changes_requested"]
    decision: Literal["approve", "request_changes"]
    summary: str | None = None
    reason: str | None = None
    suggestions: list[str] | None = None


class SubtaskRead(SQLModel):
    """Subtask payload returned from read endpoints."""

    id: UUID
    mission_id: UUID
    label: str
    description: str | None
    tool_scope: list[str] | None
    expected_output: str | None
    order: int
    status: Literal["pending", "running", "completed", "failed"]
    assigned_subagent_id: str | None
    result_summary: str | None
    result_evidence: dict[str, Any] | None
    result_risk: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MissionDispatchRequest(SQLModel):
    """Payload for dispatching a mission to OpenClaw execution engine."""

    force: bool = False


class MissionTimelineEntry(SQLModel):
    """Single entry in the mission execution timeline."""

    timestamp: datetime
    event_type: str
    stage: str
    stage_label: str
    tone: Literal["info", "success", "warning", "danger", "muted"]
    status_hint: MissionStatus | None = None
    message: str | None = None
    subtask_id: UUID | None = None
    agent_id: UUID | None = None
