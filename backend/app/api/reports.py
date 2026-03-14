"""日报/周报 API 端点。"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel import col, select

from app.api.deps import require_org_member
from app.db.session import get_session
from app.models.boards import Board
from app.schemas.reports import ReportPayload, ReportType
from app.services.organizations import OrganizationContext, list_accessible_board_ids
from app.services.watcher.report_generator import ReportGenerator

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/reports", tags=["reports"])

SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)
BOARD_ID_QUERY = Query(default=None)
GROUP_ID_QUERY = Query(default=None)


async def _resolve_board_ids(
    session: AsyncSession,
    *,
    ctx: OrganizationContext,
    board_id: UUID | None,
    group_id: UUID | None,
) -> list[UUID]:
    """解析当前用户可访问的 board_ids（与 metrics.py 逻辑一致）。"""
    board_ids = await list_accessible_board_ids(session, member=ctx.member, write=False)
    if not board_ids:
        return []
    allowed = set(board_ids)

    if board_id is not None and board_id not in allowed:
        return []

    if group_id is None:
        return [board_id] if board_id is not None else board_ids

    group_board_ids = list(
        await session.exec(
            select(Board.id)
            .where(col(Board.organization_id) == ctx.member.organization_id)
            .where(col(Board.board_group_id) == group_id)
            .where(col(Board.id).in_(board_ids)),
        ),
    )
    if board_id is not None:
        return [board_id] if board_id in set(group_board_ids) else []
    return group_board_ids


@router.get("/daily", response_model=ReportPayload)
async def daily_report(
    board_id: UUID | None = BOARD_ID_QUERY,
    group_id: UUID | None = GROUP_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ReportPayload:
    """生成过去 24 小时的日报。"""
    board_ids = await _resolve_board_ids(session, ctx=ctx, board_id=board_id, group_id=group_id)
    generator = ReportGenerator(session)
    return await generator.generate(report_type="daily", board_ids=board_ids)


@router.get("/weekly", response_model=ReportPayload)
async def weekly_report(
    board_id: UUID | None = BOARD_ID_QUERY,
    group_id: UUID | None = GROUP_ID_QUERY,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ReportPayload:
    """生成过去 7 天的周报。"""
    board_ids = await _resolve_board_ids(session, ctx=ctx, board_id=board_id, group_id=group_id)
    generator = ReportGenerator(session)
    return await generator.generate(report_type="weekly", board_ids=board_ids)
