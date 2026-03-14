"""统一 Attention 聚合服务。

把 mission / subtask / approval 的异常统一归到一个 attention 输出。
对应 backlog 3.1 的需求。
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.time import utcnow
from app.models.approvals import Approval
from app.models.boards import Board
from app.models.missions import Mission, MissionSubtask
from app.schemas.attention import (
    AttentionCategory,
    AttentionItem,
    AttentionSeverity,
    AttentionSnapshot,
)

# Stale mission 默认阈值：运行超过 2 小时未更新视为 stale
_STALE_MISSION_HOURS = 2


class AttentionCollector:
    """从 DB 聚合所有需要关注的异常项。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def collect(
        self,
        *,
        board_ids: list[UUID],
        limit: int = 50,
    ) -> AttentionSnapshot:
        """收集所有 attention 项并返回统一快照。"""
        if not board_ids:
            return self._empty_snapshot()

        failed_items = await self._failed_subtasks(board_ids, limit=limit)
        timed_out_items = await self._timed_out_subtasks(board_ids, limit=limit)
        stale_items = await self._stale_missions(board_ids, limit=limit)
        approval_items = await self._pending_approvals(board_ids, limit=limit)

        # 按 severity 排序：critical > warning > info
        all_items = failed_items + timed_out_items + stale_items + approval_items
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_items.sort(key=lambda item: (severity_order.get(item.severity, 9), item.created_at))

        return AttentionSnapshot(
            total=len(all_items),
            failed_subtasks=len(failed_items),
            timed_out_subtasks=len(timed_out_items),
            stale_missions=len(stale_items),
            pending_approvals=len(approval_items),
            items=all_items[:limit],
            generated_at=utcnow(),
        )

    async def _failed_subtasks(
        self,
        board_ids: list[UUID],
        *,
        limit: int = 50,
    ) -> list[AttentionItem]:
        """查询 status == 'failed' 的子任务。"""
        stmt = (
            select(MissionSubtask, Mission, Board)
            .join(Mission, col(Mission.id) == col(MissionSubtask.mission_id))
            .join(Board, col(Board.id) == col(Mission.board_id))
            .where(col(MissionSubtask.status) == "failed")
            .where(col(Mission.board_id).in_(board_ids))
            # 只显示 mission 未终结的失败子任务
            .where(col(Mission.status).notin_(("completed", "failed", "cancelled")))
            .order_by(col(MissionSubtask.updated_at).desc())
            .limit(limit)
        )
        rows = list((await self.session.exec(stmt)).all())
        return [
            self._item(
                category="failed_subtask",
                severity="critical",
                entity_id=subtask.id,
                entity_type="mission_subtask",
                title=f"子任务失败：{subtask.label}",
                message=subtask.error_message or "子任务执行失败，需要检查。",
                board_id=board.id,
                board_name=board.name,
                created_at=subtask.updated_at or subtask.created_at,
            )
            for subtask, mission, board in rows
        ]

    async def _timed_out_subtasks(
        self,
        board_ids: list[UUID],
        *,
        limit: int = 50,
    ) -> list[AttentionItem]:
        """查询已超时但还未被标记为 failed 的子任务。"""
        timeout_minutes = max(int(settings.mission_subtask_timeout_minutes), 1)
        cutoff = utcnow() - timedelta(minutes=timeout_minutes)

        stmt = (
            select(MissionSubtask, Mission, Board)
            .join(Mission, col(Mission.id) == col(MissionSubtask.mission_id))
            .join(Board, col(Board.id) == col(Mission.board_id))
            .where(col(MissionSubtask.status).in_(("pending", "running")))
            .where(col(MissionSubtask.updated_at) <= cutoff)
            .where(col(Mission.board_id).in_(board_ids))
            .where(col(Mission.status).notin_(("completed", "failed", "cancelled")))
            .order_by(col(MissionSubtask.updated_at).asc())
            .limit(limit)
        )
        rows = list((await self.session.exec(stmt)).all())
        return [
            self._item(
                category="timed_out_subtask",
                severity="warning",
                entity_id=subtask.id,
                entity_type="mission_subtask",
                title=f"子任务超时：{subtask.label}",
                message=f"子任务已超过 {timeout_minutes} 分钟未响应。",
                board_id=board.id,
                board_name=board.name,
                created_at=subtask.updated_at or subtask.created_at,
            )
            for subtask, mission, board in rows
        ]

    async def _stale_missions(
        self,
        board_ids: list[UUID],
        *,
        limit: int = 50,
    ) -> list[AttentionItem]:
        """查询长时间未更新的运行中 mission。"""
        cutoff = utcnow() - timedelta(hours=_STALE_MISSION_HOURS)

        stmt = (
            select(Mission, Board)
            .join(Board, col(Board.id) == col(Mission.board_id))
            .where(col(Mission.status).in_(("running", "dispatched")))
            .where(col(Mission.updated_at) <= cutoff)
            .where(col(Mission.board_id).in_(board_ids))
            .order_by(col(Mission.updated_at).asc())
            .limit(limit)
        )
        rows = list((await self.session.exec(stmt)).all())
        return [
            self._item(
                category="stale_mission",
                severity="warning",
                entity_id=mission.id,
                entity_type="mission",
                title=f"Mission 停滞：{mission.goal[:60]}",
                message=f"Mission 状态为 {mission.status}，已超过 {_STALE_MISSION_HOURS} 小时未更新。",
                board_id=board.id,
                board_name=board.name,
                created_at=mission.updated_at or mission.created_at,
            )
            for mission, board in rows
        ]

    async def _pending_approvals(
        self,
        board_ids: list[UUID],
        *,
        limit: int = 50,
    ) -> list[AttentionItem]:
        """查询待审批的 approval。"""
        stmt = (
            select(Approval, Board)
            .join(Board, col(Board.id) == col(Approval.board_id))
            .where(col(Approval.status) == "pending")
            .where(col(Approval.board_id).in_(board_ids))
            .order_by(col(Approval.created_at).desc())
            .limit(limit)
        )
        rows = list((await self.session.exec(stmt)).all())
        return [
            self._item(
                category="pending_approval",
                severity="info",
                entity_id=approval.id,
                entity_type="approval",
                title=f"待审批：{approval.action_type}",
                message=f"审批项（置信度 {approval.confidence:.0%}）等待人工确认。",
                board_id=board.id,
                board_name=board.name,
                created_at=approval.created_at,
            )
            for approval, board in rows
        ]

    @staticmethod
    def _item(
        *,
        category: AttentionCategory,
        severity: AttentionSeverity,
        entity_id: UUID,
        entity_type: str,
        title: str,
        message: str,
        board_id: UUID | None,
        board_name: str | None,
        created_at: object,
    ) -> AttentionItem:
        from datetime import datetime as _dt

        ts = created_at if isinstance(created_at, _dt) else utcnow()
        return AttentionItem(
            category=category,
            severity=severity,
            entity_id=entity_id,
            entity_type=entity_type,
            title=title,
            message=message,
            board_id=board_id,
            board_name=board_name,
            created_at=ts,
        )

    @staticmethod
    def _empty_snapshot() -> AttentionSnapshot:
        return AttentionSnapshot(
            total=0,
            failed_subtasks=0,
            timed_out_subtasks=0,
            stale_missions=0,
            pending_approvals=0,
            items=[],
            generated_at=utcnow(),
        )
