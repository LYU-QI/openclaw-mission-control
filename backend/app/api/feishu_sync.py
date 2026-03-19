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
from app.models.tasks import Task
from app.schemas.feishu_sync import (
    FeishuConflictResolutionRequest,
    FeishuSyncConfigCreate,
    FeishuSyncConfigRead,
    FeishuSyncConfigUpdate,
    FeishuSyncHistoryEntry,
    FeishuSyncTriggerResponse,
    FeishuTaskMappingRead,
)
from app.services.feishu.sync_service import SyncService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feishu-sync", tags=["feishu-sync", "agent-sync-agent"])


async def _latest_conflict_events(
    *,
    session: AsyncSession,
    board_id: UUID | None,
    task_ids: set[UUID],
) -> dict[UUID, ActivityEvent]:
    if board_id is None or not task_ids:
        return {}
    stmt = (
        select(ActivityEvent)
        .where(ActivityEvent.board_id == board_id)
        .where(ActivityEvent.task_id.in_(task_ids))
        .where(ActivityEvent.event_type == "feishu_sync_conflict")
        .order_by(ActivityEvent.created_at.desc())  # type: ignore[attr-defined]
    )
    events = list((await session.exec(stmt)).all())
    latest: dict[UUID, ActivityEvent] = {}
    for event in events:
        if event.task_id is None or event.task_id in latest:
            continue
        latest[event.task_id] = event
    return latest


async def _build_mapping_reads(
    *,
    session: AsyncSession,
    config: FeishuSyncConfig,
    mappings: list[FeishuTaskMapping],
) -> list[FeishuTaskMappingRead]:
    task_ids = {mapping.task_id for mapping in mappings}
    tasks = {}
    if task_ids:
        task_rows = list((await session.exec(select(Task).where(Task.id.in_(task_ids)))).all())
        tasks = {task.id: task for task in task_rows}
    conflict_events = await _latest_conflict_events(
        session=session,
        board_id=config.board_id,
        task_ids=task_ids,
    )
    items: list[FeishuTaskMappingRead] = []
    for mapping in mappings:
        task = tasks.get(mapping.task_id)
        conflict = conflict_events.get(mapping.task_id)
        has_conflict = bool(conflict and conflict.created_at > mapping.updated_at)
        items.append(
            FeishuTaskMappingRead(
                id=mapping.id,
                sync_config_id=mapping.sync_config_id,
                feishu_record_id=mapping.feishu_record_id,
                task_id=mapping.task_id,
                task_title=task.title if task is not None else None,
                last_feishu_update=mapping.last_feishu_update,
                last_mc_update=mapping.last_mc_update,
                sync_hash=mapping.sync_hash,
                has_conflict=has_conflict,
                conflict_at=conflict.created_at if has_conflict and conflict is not None else None,
                conflict_message=(
                    conflict.message if has_conflict and conflict is not None else None
                ),
                created_at=mapping.created_at,
                updated_at=mapping.updated_at,
            ),
        )
    return items


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
        board_mapping=payload.board_mapping,
        sync_direction=payload.sync_direction,
        sync_interval_minutes=payload.sync_interval_minutes,
        auto_dispatch=payload.auto_dispatch,
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
    from app.core.config import settings

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

        # Use Sync Agent if enabled
        if settings.enable_agent_sync:
            # Invoke Sync Agent to perform the sync
            agent_result = await sync_svc._invoke_sync_agent(
                operation="pull",
                records=None,  # Agent will fetch from Feishu
            )
            if agent_result.get("success"):
                # Agent completed successfully, use its result
                stats = agent_result.get("result", {}).get("stats", {
                    "processed": 0, "created": 0, "updated": 0, "skipped": 0, "conflicts": 0
                })
                message = "Sync completed by Sync Agent"
            else:
                # Agent failed, fall back to direct sync
                logger.warning(
                    "feishu.sync.agent_failed falling_back error=%s",
                    agent_result.get("error"),
                )
                stats = await sync_svc.pull_from_feishu()
                message = "Sync completed (agent failed, used fallback)"
        else:
            # Direct sync (default)
            stats = await sync_svc.pull_from_feishu()
            message = "Sync completed"

        return FeishuSyncTriggerResponse(
            ok=True,
            message=message,
            records_processed=stats["processed"],
            records_created=stats["created"],
            records_updated=stats["updated"],
            records_skipped=stats["skipped"],
            conflicts_count=stats["conflicts"],
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
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    stmt = (
        select(FeishuTaskMapping)
        .where(FeishuTaskMapping.sync_config_id == config_id)
        .order_by(FeishuTaskMapping.created_at.desc())  # type: ignore[attr-defined]
    )
    result = await session.exec(stmt)
    mappings = list(result.all())
    return await _build_mapping_reads(session=session, config=config, mappings=mappings)


@router.post(
    "/configs/{config_id}/mappings/{mapping_id}/resolve", response_model=FeishuTaskMappingRead
)
async def resolve_mapping_conflict(
    config_id: UUID,
    mapping_id: UUID,
    payload: FeishuConflictResolutionRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> FeishuTaskMappingRead:
    """Resolve one Feishu sync conflict from the UI."""
    config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    mapping = await FeishuTaskMapping.objects.by_id(mapping_id).first(session)
    if mapping is None or mapping.sync_config_id != config_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    sync_svc = SyncService(session, config)
    if payload.resolution == "keep_local":
        mapping = await sync_svc.resolve_conflict_keep_local(mapping)
    elif payload.resolution == "accept_feishu":
        mapping = await sync_svc.resolve_conflict_accept_feishu(mapping)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported conflict resolution action.",
        )

    items = await _build_mapping_reads(session=session, config=config, mappings=[mapping])
    return items[0]


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
            "message": (
                "Connection successful" if code == 0 else f"API error: {resp.get('msg', '')}"
            ),
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
