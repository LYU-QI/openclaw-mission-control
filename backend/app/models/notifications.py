"""Notification configuration and delivery log models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class NotificationConfig(QueryModel, table=True):
    """Notification channel and rule configuration."""

    __tablename__ = "notification_configs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)

    channel_type: str = Field(default="feishu_bot")  # feishu_bot / webhook
    channel_config: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    # List of event types that trigger notifications
    notify_on_events: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    notify_interval_minutes: int = Field(default=0)  # 0 = immediate

    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class NotificationLog(QueryModel, table=True):
    """Audit log for notification deliveries."""

    __tablename__ = "notification_logs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    notification_config_id: UUID = Field(
        foreign_key="notification_configs.id",
        index=True,
    )
    event_type: str
    channel_type: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="sent")  # sent / failed / pending_confirm
    response: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utcnow)


class NotificationTemplate(QueryModel, table=True):
    """Customizable templates for notification events."""

    __tablename__ = "notification_templates"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)

    event_type: str = Field(index=True)
    title: str
    template_type: str = Field(default="blue")  # blue, green, red, orange, etc.
    content_format: str | None = Field(default=None, sa_column=Column(Text))

    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
