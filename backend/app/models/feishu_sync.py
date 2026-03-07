"""Feishu sync configuration and task mapping models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class FeishuSyncConfig(QueryModel, table=True):
    """Configuration for syncing tasks with a Feishu Bitable spreadsheet."""

    __tablename__ = "feishu_sync_configs"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)

    # Feishu API credentials
    app_id: str
    app_secret_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    bitable_app_token: str
    bitable_table_id: str

    # Field mapping: feishu_field_name -> mc_field_name
    field_mapping: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )

    sync_direction: str = Field(default="bidirectional")  # pull_only / push_only / bidirectional
    sync_interval_minutes: int = Field(default=15)
    last_sync_at: datetime | None = None
    sync_status: str = Field(default="idle")  # idle / syncing / error
    last_error: str | None = Field(default=None, sa_column=Column(Text))

    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FeishuTaskMapping(QueryModel, table=True):
    """Maps a Feishu Bitable record to a Mission Control task."""

    __tablename__ = "feishu_task_mappings"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sync_config_id: UUID = Field(foreign_key="feishu_sync_configs.id", index=True)
    feishu_record_id: str = Field(index=True)
    task_id: UUID = Field(foreign_key="tasks.id", index=True)
    last_feishu_update: datetime | None = None
    last_mc_update: datetime | None = None
    sync_hash: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
