"""Field mapping between Feishu Bitable fields and Mission Control task fields."""

from __future__ import annotations

from typing import Any

from app.models.tasks import Task

# Default mapping when user hasn't configured a custom one
DEFAULT_FIELD_MAPPING: dict[str, str] = {
    "任务名称": "title",
    "描述": "description",
    "负责人": "owner_name",
    "优先级": "priority",
    "状态": "status",
    "截止时间": "due_at",
    "里程碑": "milestone",
}

# Reverse mapping: MC status <-> Feishu display values
STATUS_TO_FEISHU: dict[str, str] = {
    "inbox": "待处理",
    "in_progress": "进行中",
    "review": "审核中",
    "done": "已完成",
}

STATUS_FROM_FEISHU: dict[str, str] = {v: k for k, v in STATUS_TO_FEISHU.items()}

PRIORITY_TO_FEISHU: dict[str, str] = {
    "low": "低",
    "medium": "中",
    "high": "高",
    "urgent": "紧急",
}

PRIORITY_FROM_FEISHU: dict[str, str] = {v: k for k, v in PRIORITY_TO_FEISHU.items()}


class FieldMapper:
    """Transforms data between Feishu Bitable field format and MC task fields."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping = mapping or DEFAULT_FIELD_MAPPING
        self._reverse_mapping = {v: k for k, v in self.mapping.items()}

    def to_mc(self, feishu_fields: dict[str, Any]) -> dict[str, Any]:
        """Convert Feishu Bitable fields to Mission Control task attributes."""
        result: dict[str, Any] = {}
        for feishu_key, mc_key in self.mapping.items():
            value = feishu_fields.get(feishu_key)
            if value is None:
                continue

            # Handle Feishu's typed field values
            if isinstance(value, list):
                # Person fields in Feishu return as list of objects
                if value and isinstance(value[0], dict):
                    value = value[0].get("name", str(value[0].get("id", "")))
                else:
                    value = ", ".join(str(v) for v in value)

            if isinstance(value, dict):
                # Rich text fields OR single-select fields
                # Single-select might have "name" key
                if "name" in value:
                    value = value.get("name")
                else:
                    value = value.get("text", str(value))

            if mc_key == "status":
                value = STATUS_FROM_FEISHU.get(str(value), "inbox")
            elif mc_key == "priority":
                value = PRIORITY_FROM_FEISHU.get(str(value), "medium")

            result[mc_key] = value

        return result

    def to_feishu(self, task: Task) -> dict[str, Any]:
        """Convert Mission Control task to Feishu Bitable field format."""
        result: dict[str, Any] = {}
        for mc_key, feishu_key in self._reverse_mapping.items():
            value = getattr(task, mc_key, None)
            if value is None:
                continue

            if mc_key == "status":
                value = STATUS_TO_FEISHU.get(str(value), str(value))
            elif mc_key == "priority":
                value = PRIORITY_TO_FEISHU.get(str(value), str(value))
            elif hasattr(value, "isoformat"):
                value = value.isoformat()  # type: ignore[union-attr]

            result[feishu_key] = value

        # Also push result fields if they exist
        if hasattr(task, "result_summary") and task.result_summary:
            result["AI执行摘要"] = task.result_summary
        if hasattr(task, "result_risk") and task.result_risk:
            result["风险评估"] = task.result_risk
        if hasattr(task, "result_next_action") and task.result_next_action:
            result["下一步建议"] = task.result_next_action

        return result
