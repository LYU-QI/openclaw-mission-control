"""Generic queue worker with task-type dispatch."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_maker
from app.services.feishu.scheduler import schedule_feishu_sync
from app.services.feishu.queue_tasks import TASK_TYPE as FEISHU_SYNC_TASK_TYPE
from app.services.feishu.queue_tasks import (
    process_feishu_queue_task,
    requeue_feishu_queue_task,
)
from app.services.missions.subtask_timeout import fail_timed_out_subtasks
from app.services.openclaw.lifecycle_queue import TASK_TYPE as LIFECYCLE_RECONCILE_TASK_TYPE
from app.services.openclaw.lifecycle_queue import (
    requeue_lifecycle_queue_task,
)
from app.services.openclaw.lifecycle_reconcile import process_lifecycle_queue_task
from app.services.queue import QueuedTask, dequeue_task
from app.services.webhooks.dispatch import (
    process_webhook_queue_task,
    requeue_webhook_queue_task,
)
from app.services.webhooks.queue import TASK_TYPE as WEBHOOK_TASK_TYPE

logger = get_logger(__name__)
_WORKER_BLOCK_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class _TaskHandler:
    handler: Callable[[QueuedTask], Awaitable[None]]
    attempts_to_delay: Callable[[int], float]
    requeue: Callable[[QueuedTask, float], bool]


_TASK_HANDLERS: dict[str, _TaskHandler] = {
    LIFECYCLE_RECONCILE_TASK_TYPE: _TaskHandler(
        handler=process_lifecycle_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_lifecycle_queue_task(task, delay_seconds=delay),
    ),
    WEBHOOK_TASK_TYPE: _TaskHandler(
        handler=process_webhook_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_webhook_queue_task(task, delay_seconds=delay),
    ),
    FEISHU_SYNC_TASK_TYPE: _TaskHandler(
        handler=process_feishu_queue_task,
        attempts_to_delay=lambda attempts: min(
            settings.rq_dispatch_retry_base_seconds * (2 ** max(0, attempts)),
            settings.rq_dispatch_retry_max_seconds,
        ),
        requeue=lambda task, delay: requeue_feishu_queue_task(task, delay_seconds=delay),
    ),
}


def _compute_jitter(base_delay: float) -> float:
    return random.uniform(0, min(settings.rq_dispatch_retry_max_seconds / 10, base_delay * 0.1))


async def _run_feishu_scheduler_if_due(last_run_at: float) -> float:
    if not settings.feishu_sync_enabled:
        return last_run_at
    interval_seconds = max(float(settings.feishu_sync_scheduler_interval_seconds), 1.0)
    now = time.monotonic()
    if now - last_run_at < interval_seconds:
        return last_run_at
    try:
        async with async_session_maker() as session:
            queued_count = await schedule_feishu_sync(session)
        if queued_count > 0:
            logger.info(
                "queue.worker.feishu_scheduler_enqueued",
                extra={"queued_count": queued_count},
            )
    except Exception:
        logger.exception("queue.worker.feishu_scheduler_failed")
    return now


async def _run_subtask_timeout_scan_if_due(last_run_at: float) -> float:
    interval_seconds = max(float(settings.mission_subtask_scheduler_interval_seconds), 1.0)
    now = time.monotonic()
    if now - last_run_at < interval_seconds:
        return last_run_at
    try:
        async with async_session_maker() as session:
            timed_out_count = await fail_timed_out_subtasks(session)
        if timed_out_count > 0:
            logger.info(
                "queue.worker.subtask_timeout_failed",
                extra={"timed_out_count": timed_out_count},
            )
    except Exception:
        logger.exception("queue.worker.subtask_timeout_scan_failed")
    return now


async def flush_queue(*, block: bool = False, block_timeout: float = 0) -> int:
    """Consume one queue batch and dispatch by task type."""
    processed = 0
    while True:
        try:
            task = dequeue_task(
                settings.rq_queue_name,
                redis_url=settings.rq_redis_url,
                block=block,
                block_timeout=block_timeout,
            )
        except Exception:
            logger.exception(
                "queue.worker.dequeue_failed",
                extra={"queue_name": settings.rq_queue_name},
            )
            continue

        if task is None:
            break

        handler = _TASK_HANDLERS.get(task.task_type)
        if handler is None:
            logger.warning(
                "queue.worker.task_unhandled",
                extra={
                    "task_type": task.task_type,
                    "queue_name": settings.rq_queue_name,
                },
            )
            continue

        try:
            await handler.handler(task)
            processed += 1
            logger.info(
                "queue.worker.success",
                extra={
                    "task_type": task.task_type,
                    "attempt": task.attempts,
                },
            )
        except Exception as exc:
            logger.exception(
                "queue.worker.failed",
                extra={
                    "task_type": task.task_type,
                    "attempt": task.attempts,
                    "error": str(exc),
                },
            )
            base_delay = handler.attempts_to_delay(task.attempts)
            delay = base_delay + _compute_jitter(base_delay)
            if not handler.requeue(task, delay):
                logger.warning(
                    "queue.worker.drop_task",
                    extra={
                        "task_type": task.task_type,
                        "attempt": task.attempts,
                    },
                )
        await asyncio.sleep(settings.rq_dispatch_throttle_seconds)

    if processed > 0:
        logger.info("queue.worker.batch_complete", extra={"count": processed})
    return processed


async def _run_worker_loop() -> None:
    scheduler_last_run_at = 0.0
    timeout_scan_last_run_at = 0.0
    while True:
        try:
            scheduler_last_run_at = await _run_feishu_scheduler_if_due(scheduler_last_run_at)
            timeout_scan_last_run_at = await _run_subtask_timeout_scan_if_due(
                timeout_scan_last_run_at
            )
            await flush_queue(
                block=True,
                # Keep a finite timeout so scheduled tasks are periodically drained.
                block_timeout=_WORKER_BLOCK_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "queue.worker.loop_failed",
                extra={"queue_name": settings.rq_queue_name},
            )
            await asyncio.sleep(1)


def run_worker() -> None:
    """RQ entrypoint for running continuous queue processing."""
    logger.info(
        "queue.worker.batch_started",
        extra={"throttle_seconds": settings.rq_dispatch_throttle_seconds},
    )
    try:
        asyncio.run(_run_worker_loop())
    finally:
        logger.info("queue.worker.stopped", extra={"queue_name": settings.rq_queue_name})
