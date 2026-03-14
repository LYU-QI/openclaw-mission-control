"""统一 Attention 快照 schema，用于聚合需要关注的系统异常。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)

AttentionSeverity = Literal["critical", "warning", "info"]
AttentionCategory = Literal[
    "failed_subtask",
    "timed_out_subtask",
    "stale_mission",
    "pending_approval",
]


class AttentionItem(SQLModel):
    """单条 attention 记录。"""

    category: AttentionCategory
    severity: AttentionSeverity
    entity_id: UUID
    entity_type: str
    title: str
    message: str
    board_id: UUID | None = None
    board_name: str | None = None
    created_at: datetime


class AttentionSnapshot(SQLModel):
    """Dashboard attention 聚合快照。"""

    total: int
    failed_subtasks: int
    timed_out_subtasks: int
    stale_missions: int
    pending_approvals: int
    items: list[AttentionItem]
    generated_at: datetime
