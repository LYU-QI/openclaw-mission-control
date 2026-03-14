"""日报/周报结构化 schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime,)

ReportType = Literal["daily", "weekly"]


class ReportMetric(SQLModel):
    """报告中的单个指标。"""

    label: str
    value: str
    change: str | None = None
    tone: Literal["success", "warning", "danger", "info", "muted"] = "info"


class ReportSection(SQLModel):
    """报告中的一个段落。"""

    title: str
    content: str
    metrics: list[ReportMetric] = []


class ReportPayload(SQLModel):
    """完整的日报/周报响应体。"""

    report_type: ReportType
    period_start: datetime
    period_end: datetime
    summary: str
    sections: list[ReportSection]
    generated_at: datetime
