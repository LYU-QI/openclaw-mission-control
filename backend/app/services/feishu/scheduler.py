"""RQ enqueue helpers for periodic Feishu sync."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.feishu_sync import FeishuSyncConfig
from app.services.queue import QueuedTask, enqueue_task


def _should_sync(config: FeishuSyncConfig) -> bool:
    if not config.enabled:
        return False
    if config.last_sync_at is None:
        return True
    interval_minutes = config.sync_interval_minutes
    if interval_minutes <= 0:
        interval_minutes = settings.feishu_sync_default_interval_minutes
    interval = timedelta(minutes=max(interval_minutes, 1))
    return utcnow() - config.last_sync_at >= interval


async def schedule_feishu_sync(session: AsyncSession) -> int:
    """Enqueue sync jobs for eligible configurations."""
    stmt = select(FeishuSyncConfig).where(FeishuSyncConfig.enabled.is_(True))
    configs = list((await session.exec(stmt)).all())
    queued = 0
    for config in configs:
        if not _should_sync(config):
            continue
        enqueue_task(
            QueuedTask(
                task_type="feishu.sync",
                payload={"config_id": str(config.id)},
                created_at=utcnow(),
            ),
            queue_name="default",
        )
        queued += 1
    return queued
