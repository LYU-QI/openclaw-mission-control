"""Feishu sync configuration and trigger API endpoints."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import AUTH_DEP, SESSION_DEP
from app.core.secrets import decrypt_secret, encrypt_secret
from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.feishu_sync import FeishuSyncConfig, FeishuTaskMapping
from app.schemas.feishu_sync import (
    FeishuSyncConfigCreate,
    FeishuSyncConfigRead,
    FeishuSyncHistoryEntry,
    FeishuSyncConfigUpdate,
    FeishuSyncTriggerResponse,
    FeishuTaskMappingRead,
)
from app.services.feishu.sync_service import SyncService

if TYPE_CHECKING:
    from app.core.auth import AuthContext
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feishu-sync", tags=["feishu-sync"])


@router.post("/configs", response_model=FeishuSyncConfigRead, status_code=status.HTTP_201_CREATED)
async def create_sync_config(
    payload: FeishuSyncConfigCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FeishuSyncConfig:
    """Create a new Feishu sync configuration."""
    config = FeishuSyncConfig(
        organization_id=payload.organization_id,
        board_id=payload.board_id,
        app_id=payload.app_id,
        app_secret_encrypted=encrypt_secret(payload.app_secret),
        bitable_app_token=payload.bitable_app_token,
        bitable_table_id=payload.bitable_table_id,
        field_mapping=payload.field_mapping,
        sync_direction=payload.sync_direction,
        sync_interval_minutes=payload.sync_interval_minutes,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.get("/configs", response_model=list[FeishuSyncConfigRead])
async def list_sync_configs(
    organization_id: UUID | None = None,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[FeishuSyncConfig]:
    """List Feishu sync configurations."""
    stmt = select(FeishuSyncConfig).order_by(FeishuSyncConfig.created_at.desc())  # type: ignore[attr-defined]
    if organization_id:
        stmt = stmt.where(FeishuSyncConfig.organization_id == organization_id)
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/configs/{config_id}", response_model=FeishuSyncConfigRead)
async def get_sync_config(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FeishuSyncConfig:
    """Retrieve a sync configuration by ID."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config


@router.patch("/configs/{config_id}", response_model=FeishuSyncConfigRead)
async def update_sync_config(
    config_id: UUID,
    payload: FeishuSyncConfigUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FeishuSyncConfig:
    """Update a sync configuration."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)
    if "app_secret" in update_data:
        update_data["app_secret_encrypted"] = encrypt_secret(update_data.pop("app_secret"))
    for key, value in update_data.items():
        setattr(config, key, value)
    config.updated_at = utcnow()
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sync_config(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> None:
    """Delete a sync configuration."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await session.delete(config)
    await session.commit()


@router.post("/configs/{config_id}/trigger", response_model=FeishuSyncTriggerResponse)
async def trigger_sync(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FeishuSyncTriggerResponse:
    """Manually trigger a Feishu sync."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    config.sync_status = "syncing"
    config.updated_at = utcnow()
    session.add(config)
    await session.commit()
    await session.refresh(config)

    try:
        sync_svc = SyncService(session, config)
        stats = await sync_svc.pull_from_feishu()
        return FeishuSyncTriggerResponse(
            ok=True,
            message="Sync completed",
            records_processed=stats["processed"],
            records_created=stats["created"],
            records_updated=stats["updated"],
        )
    except Exception as e:
        logger.exception("Feishu sync failed for config %s", config_id)
        config.sync_status = "error"
        config.last_error = str(e)
        config.updated_at = utcnow()
        session.add(config)
        await session.commit()
        return FeishuSyncTriggerResponse(ok=False, message=str(e))


@router.get("/configs/{config_id}/mappings", response_model=list[FeishuTaskMappingRead])
async def list_mappings(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[FeishuTaskMapping]:
    """List task mappings for a sync configuration."""
    stmt = (
        select(FeishuTaskMapping)
        .where(FeishuTaskMapping.sync_config_id == config_id)
        .order_by(FeishuTaskMapping.created_at.desc())  # type: ignore[attr-defined]
    )
    result = await session.exec(stmt)
    return list(result.all())


@router.post("/configs/{config_id}/test")
async def test_connection(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> dict:
    """Test the Feishu API connection for a sync config."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        from app.services.feishu.client import FeishuClient

        client = FeishuClient(config.app_id, decrypt_secret(config.app_secret_encrypted))
        resp = client.list_bitable_records(
            config.bitable_app_token,
            config.bitable_table_id,
            page_size=1,
        )
        code = resp.get("code", -1)
        return {
            "ok": code == 0,
            "message": "Connection successful" if code == 0 else f"API error: {resp.get('msg', '')}",
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}


@router.get("/configs/{config_id}/history", response_model=list[FeishuSyncHistoryEntry])
async def sync_history(
    config_id: UUID,
    limit: int = 50,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[FeishuSyncHistoryEntry]:
    """Return recent sync history entries from activity log."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    stmt = (
        select(ActivityEvent)
        .where(ActivityEvent.board_id == config.board_id)
        .where(ActivityEvent.event_type.in_(["feishu_sync_pull", "feishu_sync_push"]))
        .order_by(ActivityEvent.created_at.desc())  # type: ignore[attr-defined]
        .limit(limit)
    )
    events = list((await session.exec(stmt)).all())
    history: list[FeishuSyncHistoryEntry] = []
    for event in events:
        direction = "pull" if event.event_type == "feishu_sync_pull" else "push"
        history.append(
            FeishuSyncHistoryEntry(
                timestamp=event.created_at,
                direction=direction,
                records_processed=0,
                status="ok",
                error=None,
            ),
        )
    return history
