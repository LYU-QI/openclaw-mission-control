"""Schemas for notification configuration and log API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class NotificationConfigCreate(SQLModel):
    """Payload for creating a notification configuration."""

    organization_id: UUID
    board_id: UUID | None = None
    channel_type: str = "feishu_bot"
    channel_config: dict[str, Any] = {}
    notify_on_events: list[str] = []
    notify_interval_minutes: int = 0
    enabled: bool = True


class NotificationConfigUpdate(SQLModel):
    """Payload for updating a notification configuration."""

    board_id: UUID | None = None
    channel_type: str | None = None
    channel_config: dict[str, Any] | None = None
    notify_on_events: list[str] | None = None
    notify_interval_minutes: int | None = None
    enabled: bool | None = None


class NotificationConfigRead(SQLModel):
    """Notification configuration returned from read endpoints."""

    id: UUID
    organization_id: UUID
    board_id: UUID | None
    channel_type: str
    channel_config: dict[str, Any]
    notify_on_events: list[str]
    notify_interval_minutes: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationLogRead(SQLModel):
    """Notification delivery log returned from read endpoints."""

    id: UUID
    notification_config_id: UUID
    event_type: str
    channel_type: str
    payload: dict[str, Any]
    status: str
    response: dict[str, Any] | None
    error_message: str | None
    created_at: datetime


class NotificationTestResponse(SQLModel):
    """Response from a test notification send."""

    ok: bool
    message: str = ""
