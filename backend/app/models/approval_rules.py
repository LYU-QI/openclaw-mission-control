"""Approval triggering rules for mission control."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class ApprovalRule(QueryModel, table=True):
    """Configuration rule governing automatic approval triggers."""

    __tablename__ = "approval_rules"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)

    # 规则名称与描述
    name: str
    description: str | None = None

    # 触发条件
    trigger_on_high_risk: bool = Field(default=False)
    trigger_on_tool_usage: str | None = None  # Comma separated tool names or wildcard
    trigger_on_domain: str | None = None  # Optional domain target restriction

    # 审批策略覆盖
    override_policy: str = Field(default="post_review")  # auto / block / pre_approve / post_review

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
