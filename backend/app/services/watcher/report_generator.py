"""日报/周报生成服务。

对应 backlog 3.2 的需求：先做服务，不急着做人格化 Watcher Agent。
汇总 throughput、error rate、attention items、mission 完成情况。
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import case, func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.missions import Mission, MissionSubtask
from app.models.tasks import Task
from app.schemas.reports import (
    ReportMetric,
    ReportPayload,
    ReportSection,
    ReportType,
)
from app.services.watcher.attention import AttentionCollector

# 错误事件匹配模式，与 metrics.py 保持一致
_ERROR_EVENT_PATTERN = "%failed"


class ReportGenerator:
    """生成结构化的日报/周报。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(
        self,
        *,
        report_type: ReportType,
        board_ids: list[UUID],
    ) -> ReportPayload:
        """根据类型生成日报或周报。"""
        now = utcnow()
        if report_type == "daily":
            period_start = now - timedelta(hours=24)
            period_label = "过去 24 小时"
        else:
            period_start = now - timedelta(days=7)
            period_label = "过去 7 天"

        sections: list[ReportSection] = []

        # 1. 任务统计
        task_section = await self._task_summary_section(board_ids, period_start, now, period_label)
        sections.append(task_section)

        # 2. Mission 执行统计
        mission_section = await self._mission_summary_section(
            board_ids, period_start, now, period_label
        )
        sections.append(mission_section)

        # 3. 错误与异常
        error_section = await self._error_section(board_ids, period_start, now, period_label)
        sections.append(error_section)

        # 4. Attention 快照
        attention_section = await self._attention_section(board_ids)
        sections.append(attention_section)

        # 构建摘要
        summary = self._build_summary(sections, period_label)

        return ReportPayload(
            report_type=report_type,
            period_start=period_start,
            period_end=now,
            summary=summary,
            sections=sections,
            generated_at=now,
        )

    async def _task_summary_section(
        self,
        board_ids: list[UUID],
        start: object,
        end: object,
        period_label: str,
    ) -> ReportSection:
        """汇总任务完成情况。"""
        metrics: list[ReportMetric] = []

        if not board_ids:
            return ReportSection(
                title="📋 任务概览",
                content=f"{period_label}无可用数据。",
                metrics=metrics,
            )

        # 已完成数
        done_count = await self._count_tasks_in_status(board_ids, "done", start, end)
        metrics.append(ReportMetric(label="已完成任务", value=str(done_count), tone="success"))

        # 新建数
        new_count = await self._count_new_tasks(board_ids, start, end)
        metrics.append(ReportMetric(label="新建任务", value=str(new_count), tone="info"))

        # 当前进行中
        in_progress = await self._count_tasks_current_status(board_ids, "in_progress")
        metrics.append(ReportMetric(label="进行中任务", value=str(in_progress), tone="info"))

        # 待审核
        review = await self._count_tasks_current_status(board_ids, "review")
        metrics.append(
            ReportMetric(
                label="待审核任务", value=str(review), tone="warning" if review > 0 else "info"
            )
        )

        return ReportSection(
            title="📋 任务概览",
            content=f"{period_label}共完成 {done_count} 项任务，新建 {new_count} 项。当前 {in_progress} 项进行中，{review} 项待审核。",
            metrics=metrics,
        )

    async def _mission_summary_section(
        self,
        board_ids: list[UUID],
        start: object,
        end: object,
        period_label: str,
    ) -> ReportSection:
        """汇总 mission 执行情况。"""
        metrics: list[ReportMetric] = []

        if not board_ids:
            return ReportSection(
                title="🚀 Mission 执行",
                content=f"{period_label}无可用数据。",
                metrics=metrics,
            )

        # Mission 统计
        stmt = (
            select(col(Mission.status), func.count())
            .where(col(Mission.board_id).in_(board_ids))
            .where(col(Mission.updated_at) >= start)
            .where(col(Mission.updated_at) <= end)
            .group_by(col(Mission.status))
        )
        results = list((await self.session.exec(stmt)).all())
        status_counts: dict[str, int] = {}
        for status_val, count in results:
            status_counts[str(status_val)] = int(count or 0)

        completed = status_counts.get("completed", 0)
        failed = status_counts.get("failed", 0)
        running = status_counts.get("running", 0)
        total = sum(status_counts.values())

        metrics.append(ReportMetric(label="Mission 总数", value=str(total), tone="info"))
        metrics.append(ReportMetric(label="已完成", value=str(completed), tone="success"))
        metrics.append(
            ReportMetric(
                label="失败",
                value=str(failed),
                tone="danger" if failed > 0 else "muted",
            )
        )
        metrics.append(ReportMetric(label="执行中", value=str(running), tone="info"))

        # 子任务失败数
        failed_subtasks_stmt = (
            select(func.count())
            .select_from(MissionSubtask)
            .join(Mission, col(Mission.id) == col(MissionSubtask.mission_id))
            .where(col(MissionSubtask.status) == "failed")
            .where(col(Mission.board_id).in_(board_ids))
            .where(col(MissionSubtask.updated_at) >= start)
            .where(col(MissionSubtask.updated_at) <= end)
        )
        failed_subtask_count = int((await self.session.exec(failed_subtasks_stmt)).one() or 0)
        if failed_subtask_count > 0:
            metrics.append(
                ReportMetric(
                    label="失败子任务",
                    value=str(failed_subtask_count),
                    tone="danger",
                )
            )

        return ReportSection(
            title="🚀 Mission 执行",
            content=(
                f"{period_label}共 {total} 个 mission 有活动，"
                f"{completed} 个完成，{failed} 个失败，{running} 个执行中。"
            ),
            metrics=metrics,
        )

    async def _error_section(
        self,
        board_ids: list[UUID],
        start: object,
        end: object,
        period_label: str,
    ) -> ReportSection:
        """汇总错误和异常事件。"""
        metrics: list[ReportMetric] = []

        if not board_ids:
            return ReportSection(
                title="⚠️ 错误与异常",
                content=f"{period_label}无可用数据。",
                metrics=metrics,
            )

        error_case = case(
            (col(ActivityEvent.event_type).like(_ERROR_EVENT_PATTERN), 1),
            else_=0,
        )
        stmt = (
            select(func.sum(error_case), func.count())
            .join(Task, col(ActivityEvent.task_id) == col(Task.id))
            .where(col(ActivityEvent.created_at) >= start)
            .where(col(ActivityEvent.created_at) <= end)
            .where(col(Task.board_id).in_(board_ids))
        )
        result = (await self.session.exec(stmt)).one_or_none()
        if result is None:
            errors, total = 0, 0
        else:
            errors, total = int(result[0] or 0), int(result[1] or 0)

        error_rate = (errors / total * 100) if total > 0 else 0.0
        metrics.append(ReportMetric(label="总事件数", value=str(total), tone="info"))
        metrics.append(
            ReportMetric(
                label="错误事件",
                value=str(errors),
                tone="danger" if errors > 0 else "success",
            )
        )
        metrics.append(
            ReportMetric(
                label="错误率",
                value=f"{error_rate:.1f}%",
                tone="danger" if error_rate > 5 else ("warning" if error_rate > 1 else "success"),
            )
        )

        return ReportSection(
            title="⚠️ 错误与异常",
            content=f"{period_label}共 {total} 个事件，其中 {errors} 个错误事件（错误率 {error_rate:.1f}%）。",
            metrics=metrics,
        )

    async def _attention_section(
        self,
        board_ids: list[UUID],
    ) -> ReportSection:
        """当前系统 attention 快照摘要。"""
        collector = AttentionCollector(self.session)
        snapshot = await collector.collect(board_ids=board_ids, limit=10)

        metrics = [
            ReportMetric(
                label="需关注总数",
                value=str(snapshot.total),
                tone="warning" if snapshot.total > 0 else "success",
            ),
            ReportMetric(
                label="失败子任务",
                value=str(snapshot.failed_subtasks),
                tone="danger" if snapshot.failed_subtasks > 0 else "muted",
            ),
            ReportMetric(
                label="超时子任务",
                value=str(snapshot.timed_out_subtasks),
                tone="warning" if snapshot.timed_out_subtasks > 0 else "muted",
            ),
            ReportMetric(
                label="停滞 Mission",
                value=str(snapshot.stale_missions),
                tone="warning" if snapshot.stale_missions > 0 else "muted",
            ),
            ReportMetric(
                label="待审批",
                value=str(snapshot.pending_approvals),
                tone="info" if snapshot.pending_approvals > 0 else "muted",
            ),
        ]

        if snapshot.total == 0:
            content = "当前系统运行正常，无需特别关注的项。"
        else:
            content = f"当前有 {snapshot.total} 个需要关注的项，请及时处理。"

        return ReportSection(
            title="🔔 需要关注",
            content=content,
            metrics=metrics,
        )

    def _build_summary(self, sections: list[ReportSection], period_label: str) -> str:
        """从各 section 生成一行摘要。"""
        parts: list[str] = []
        for section in sections:
            if section.metrics:
                highlights = [
                    f"{m.label}: {m.value}"
                    for m in section.metrics
                    if m.tone in ("danger", "warning", "success")
                ]
                if highlights:
                    parts.append("、".join(highlights[:3]))
        if parts:
            return f"{period_label}摘要 — " + "；".join(parts) + "。"
        return f"{period_label}暂无异常。"

    # ---- 辅助查询 ----

    async def _count_tasks_in_status(
        self,
        board_ids: list[UUID],
        status: str,
        start: object,
        end: object,
    ) -> int:
        stmt = (
            select(func.count())
            .where(col(Task.status) == status)
            .where(col(Task.board_id).in_(board_ids))
            .where(col(Task.updated_at) >= start)
            .where(col(Task.updated_at) <= end)
        )
        return int((await self.session.exec(stmt)).one() or 0)

    async def _count_new_tasks(
        self,
        board_ids: list[UUID],
        start: object,
        end: object,
    ) -> int:
        stmt = (
            select(func.count())
            .where(col(Task.board_id).in_(board_ids))
            .where(col(Task.created_at) >= start)
            .where(col(Task.created_at) <= end)
        )
        return int((await self.session.exec(stmt)).one() or 0)

    async def _count_tasks_current_status(
        self,
        board_ids: list[UUID],
        status: str,
    ) -> int:
        stmt = (
            select(func.count())
            .where(col(Task.status) == status)
            .where(col(Task.board_id).in_(board_ids))
        )
        return int((await self.session.exec(stmt)).one() or 0)
