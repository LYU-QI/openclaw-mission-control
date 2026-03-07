"""Mission and subtask models for AI task execution pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Mission(QueryModel, table=True):
    """AI execution unit derived from a Task, dispatched to OpenClaw."""

    __tablename__ = "missions"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    board_id: UUID = Field(foreign_key="boards.id", index=True)
    agent_id: UUID | None = Field(default=None, foreign_key="agents.id", index=True)

    # Mission definition
    goal: str = Field(sa_column=Column(Text, nullable=False))
    constraints: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    context_refs: list[str] | None = Field(default=None, sa_column=Column(JSON))

    # Approval policy: auto / pre_approve / post_review
    approval_policy: str = Field(default="auto")
    approval_id: UUID | None = Field(default=None, foreign_key="approvals.id")

    # Execution status
    # pending -> dispatched -> running -> aggregating -> completed / failed / pending_approval
    status: str = Field(default="pending", index=True)
    dispatched_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Execution result
    result_summary: str | None = Field(default=None, sa_column=Column(Text))
    result_evidence: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result_risk: str | None = None
    result_next_action: str | None = Field(default=None, sa_column=Column(Text))

    # Retry metadata
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    error_message: str | None = Field(default=None, sa_column=Column(Text))

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MissionSubtask(QueryModel, table=True):
    """Subtask decomposed from a Mission for parallel execution."""

    __tablename__ = "mission_subtasks"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    mission_id: UUID = Field(foreign_key="missions.id", index=True)

    label: str
    description: str | None = Field(default=None, sa_column=Column(Text))
    tool_scope: list[str] | None = Field(default=None, sa_column=Column(JSON))
    expected_output: str | None = Field(default=None, sa_column=Column(Text))
    order: int = Field(default=0)

    # Execution status: pending -> running -> completed / failed
    status: str = Field(default="pending", index=True)
    assigned_subagent_id: str | None = None

    # Result
    result_summary: str | None = Field(default=None, sa_column=Column(Text))
    result_evidence: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    result_risk: str | None = None
    error_message: str | None = Field(default=None, sa_column=Column(Text))

    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
