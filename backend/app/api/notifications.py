"""Notification configuration and log API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import AUTH_DEP, SESSION_DEP
from app.core.time import utcnow
from app.models.notifications import NotificationConfig, NotificationLog, NotificationTemplate
from app.schemas.notifications import (
    NotificationConfigCreate,
    NotificationConfigRead,
    NotificationConfigUpdate,
    NotificationConfirmRequest,
    NotificationConfirmResponse,
    NotificationLogRead,
    NotificationTemplateCreate,
    NotificationTemplateRead,
    NotificationTemplateUpdate,
    NotificationTestResponse,
)
from app.services.notification.notification_service import NotificationService

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "/configs",
    response_model=NotificationConfigRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_config(
    payload: NotificationConfigCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationConfig:
    """Create a notification channel configuration."""
    config = NotificationConfig(
        organization_id=payload.organization_id,
        board_id=payload.board_id,
        name=payload.name,
        channel_type=payload.channel_type,
        channel_config=payload.channel_config,
        notify_on_events=payload.notify_on_events,
        notify_interval_minutes=payload.notify_interval_minutes,
        enabled=payload.enabled,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.get("/configs", response_model=list[NotificationConfigRead])
async def list_notification_configs(
    organization_id: UUID | None = None,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[NotificationConfig]:
    """List notification configurations."""
    stmt = select(NotificationConfig).order_by(
        NotificationConfig.created_at.desc(),  # type: ignore[attr-defined]
    )
    if organization_id:
        stmt = stmt.where(NotificationConfig.organization_id == organization_id)
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/configs/{config_id}", response_model=NotificationConfigRead)
async def get_notification_config(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationConfig:
    """Retrieve a notification configuration."""
    config = await NotificationConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return config


@router.patch("/configs/{config_id}", response_model=NotificationConfigRead)
async def update_notification_config(
    config_id: UUID,
    payload: NotificationConfigUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationConfig:
    """Update a notification configuration."""
    config = await NotificationConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    config.updated_at = utcnow()
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_config(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> None:
    """Delete a notification configuration."""
    from sqlmodel import select
    from app.models.notifications import NotificationLog

    config = await NotificationConfig.objects.by_id(config_id).first(session)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Delete associated notification logs first (foreign key constraint)
    logs_stmt = select(NotificationLog).where(
        NotificationLog.notification_config_id == config_id
    )
    logs = await session.exec(logs_stmt)
    for log in logs.all():
        await session.delete(log)

    await session.delete(config)
    await session.commit()


@router.post("/configs/{config_id}/test", response_model=NotificationTestResponse)
async def test_notification(
    config_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationTestResponse:
    """Send a test notification via the configured channel."""
    svc = NotificationService(session)
    result = await svc.test_notification(config_id)
    return NotificationTestResponse(ok=result["ok"], message=result["message"])


@router.get("/logs", response_model=list[NotificationLogRead])
async def list_notification_logs(
    config_id: UUID | None = None,
    event_type: str | None = None,
    limit: int = 50,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[NotificationLog]:
    """List notification delivery logs."""
    stmt = (
        select(NotificationLog)
        .order_by(
            NotificationLog.created_at.desc(),  # type: ignore[attr-defined]
        )
        .limit(limit)
    )
    if config_id:
        stmt = stmt.where(NotificationLog.notification_config_id == config_id)
    if event_type:
        stmt = stmt.where(NotificationLog.event_type == event_type)
    result = await session.exec(stmt)
    return list(result.all())


@router.post("/confirm/{log_id}", response_model=NotificationConfirmResponse)
async def confirm_notification(
    log_id: UUID,
    payload: NotificationConfirmRequest,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationConfirmResponse:
    """Handle manual confirmation callbacks for pending notifications."""
    log = await NotificationLog.objects.by_id(log_id).first(session)
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    status_map = {
        "confirmed": "sent",
        "approved": "sent",
        "rejected": "failed",
        "dismissed": "failed",
    }
    log.status = status_map.get(payload.action.lower(), log.status)
    log.error_message = payload.comment if log.status == "failed" else None
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return NotificationConfirmResponse(
        ok=True,
        status=log.status,
        message="Confirmation recorded",
    )


@router.post(
    "/templates",
    response_model=NotificationTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification_template(
    payload: NotificationTemplateCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationTemplate:
    """Create a notification template."""
    template = NotificationTemplate(
        organization_id=payload.organization_id,
        event_type=payload.event_type,
        title=payload.title,
        template_type=payload.template_type,
        content_format=payload.content_format,
        is_active=payload.is_active,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.get("/templates", response_model=list[NotificationTemplateRead])
async def list_notification_templates(
    organization_id: UUID | None = None,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> list[NotificationTemplate]:
    """List notification templates."""
    stmt = select(NotificationTemplate).order_by(
        NotificationTemplate.created_at.desc(),  # type: ignore[attr-defined]
    )
    if organization_id:
        stmt = stmt.where(NotificationTemplate.organization_id == organization_id)
    result = await session.exec(stmt)
    return list(result.all())


@router.get("/templates/{template_id}", response_model=NotificationTemplateRead)
async def get_notification_template(
    template_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationTemplate:
    """Retrieve a notification template."""
    template = await NotificationTemplate.objects.by_id(template_id).first(session)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return template


@router.patch("/templates/{template_id}", response_model=NotificationTemplateRead)
async def update_notification_template(
    template_id: UUID,
    payload: NotificationTemplateUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> NotificationTemplate:
    """Update a notification template."""
    template = await NotificationTemplate.objects.by_id(template_id).first(session)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(template, key, value)
    template.updated_at = utcnow()
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification_template(
    template_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
) -> None:
    """Delete a notification template."""
    template = await NotificationTemplate.objects.by_id(template_id).first(session)
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await session.delete(template)
    await session.commit()
