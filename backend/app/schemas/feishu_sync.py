"""Schemas for Feishu sync configuration and mapping API payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import Field, SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class FeishuSyncConfigCreate(SQLModel):
    """Payload for creating a Feishu sync configuration."""

    organization_id: UUID
    board_id: UUID | None = None
    app_id: str
    app_secret: str  # plaintext; encrypted before storage
    bitable_app_token: str
    bitable_table_id: str
    field_mapping: dict[str, Any] = Field(default_factory=dict)
    sync_direction: str = "bidirectional"
    sync_interval_minutes: int = 15


class FeishuSyncConfigUpdate(SQLModel):
    """Payload for updating a Feishu sync configuration."""

    board_id: UUID | None = None
    app_id: str | None = None
    app_secret: str | None = None
    bitable_app_token: str | None = None
    bitable_table_id: str | None = None
    field_mapping: dict[str, Any] | None = None
    sync_direction: str | None = None
    sync_interval_minutes: int | None = None
    enabled: bool | None = None


class FeishuSyncConfigRead(SQLModel):
    """Feishu sync configuration returned from read endpoints."""

    id: UUID
    organization_id: UUID
    board_id: UUID | None
    app_id: str
    bitable_app_token: str
    bitable_table_id: str
    field_mapping: dict[str, Any]
    sync_direction: str
    sync_interval_minutes: int
    last_sync_at: datetime | None
    sync_status: str
    last_error: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class FeishuTaskMappingRead(SQLModel):
    """Feishu-to-MC task mapping returned from read endpoints."""

    id: UUID
    sync_config_id: UUID
    feishu_record_id: str
    task_id: UUID
    last_feishu_update: datetime | None
    last_mc_update: datetime | None
    sync_hash: str | None
    created_at: datetime
    updated_at: datetime


class FeishuSyncTriggerResponse(SQLModel):
    """Response after triggering a manual sync."""

    ok: bool = True
    message: str = "sync triggered"
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0


class FeishuSyncHistoryEntry(SQLModel):
    """A single sync history log entry."""

    timestamp: datetime
    direction: str
    records_processed: int
    status: str
    error: str | None = None
