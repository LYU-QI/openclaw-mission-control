"""Feishu writeback helpers for mission/task results."""

from __future__ import annotations

from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.feishu_sync import FeishuSyncConfig
from app.services.feishu.sync_service import SyncService


class WritebackService:
    """Pushes task execution results back to Feishu Bitable records."""

    def __init__(self, session: AsyncSession, config: FeishuSyncConfig) -> None:
        self._sync_service = SyncService(session, config)

    async def push_task_result(self, task_id: UUID) -> bool:
        """Write a task result to Feishu when a mapping exists."""
        return await self._sync_service.push_to_feishu(task_id)

