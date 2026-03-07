"""Background queue handlers for Feishu sync tasks."""

from __future__ import annotations

from uuid import UUID

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.feishu_sync import FeishuSyncConfig
from app.services.feishu.sync_service import SyncService
from app.services.queue import QueuedTask, requeue_if_failed

TASK_TYPE = "feishu.sync"


async def process_feishu_queue_task(task: QueuedTask) -> None:
    """Execute a queued Feishu sync task."""
    config_id_raw = task.payload.get("config_id")
    if not isinstance(config_id_raw, str):
        raise ValueError("config_id is required")
    config_id = UUID(config_id_raw)
    async with async_session_maker() as session:
        config = await FeishuSyncConfig.objects.by_id(config_id).first(session)
        if config is None or not config.enabled:
            return
        await SyncService(session, config).pull_from_feishu()


def requeue_feishu_queue_task(task: QueuedTask, *, delay_seconds: float) -> bool:
    """Requeue a failed Feishu sync task."""
    return requeue_if_failed(
        task,
        settings.rq_queue_name,
        max_retries=settings.rq_dispatch_max_retries,
        redis_url=settings.rq_redis_url,
        delay_seconds=delay_seconds,
    )

