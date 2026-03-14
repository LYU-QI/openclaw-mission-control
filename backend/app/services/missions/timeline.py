"""Structured mission timeline metadata helpers."""

from __future__ import annotations

from typing import Final

TIMELINE_EVENT_META: Final[dict[str, dict[str, str | None]]] = {
    "mission_created": {
        "stage": "created",
        "stage_label": "已创建",
        "status_hint": "pending",
        "tone": "info",
    },
    "mission_dispatched": {
        "stage": "dispatch",
        "stage_label": "已下发",
        "status_hint": "dispatched",
        "tone": "info",
    },
    "mission_started": {
        "stage": "execution",
        "stage_label": "执行中",
        "status_hint": "running",
        "tone": "info",
    },
    "mission_completed": {
        "stage": "result",
        "stage_label": "已完成",
        "status_hint": "completed",
        "tone": "success",
    },
    "mission_failed": {
        "stage": "result",
        "stage_label": "已失败",
        "status_hint": "failed",
        "tone": "danger",
    },
    "mission_cancelled": {
        "stage": "result",
        "stage_label": "已取消",
        "status_hint": "cancelled",
        "tone": "muted",
    },
    "approval_requested": {
        "stage": "approval",
        "stage_label": "待审批",
        "status_hint": "pending_approval",
        "tone": "warning",
    },
    "approval_granted": {
        "stage": "approval",
        "stage_label": "审批通过",
        "status_hint": "completed",
        "tone": "success",
    },
    "approval_rejected": {
        "stage": "approval",
        "stage_label": "审批拒绝",
        "status_hint": "failed",
        "tone": "danger",
    },
    "subtask_created": {
        "stage": "subtask",
        "stage_label": "子任务已创建",
        "status_hint": None,
        "tone": "info",
    },
    "subtask_dispatched": {
        "stage": "subtask",
        "stage_label": "子任务已下发",
        "status_hint": None,
        "tone": "info",
    },
    "subtask_started": {
        "stage": "subtask",
        "stage_label": "子任务执行中",
        "status_hint": "running",
        "tone": "info",
    },
    "subtask_completed": {
        "stage": "subtask",
        "stage_label": "子任务完成",
        "status_hint": "completed",
        "tone": "success",
    },
    "subtask_failed": {
        "stage": "subtask",
        "stage_label": "子任务失败",
        "status_hint": "failed",
        "tone": "danger",
    },
    "subtask_redispatched": {
        "stage": "subtask",
        "stage_label": "子任务重派",
        "status_hint": "pending",
        "tone": "warning",
    },
}


def timeline_meta_for_event(event_type: str) -> dict[str, str | None]:
    return TIMELINE_EVENT_META.get(
        event_type,
        {
            "stage": "other",
            "stage_label": "其他事件",
            "status_hint": None,
            "tone": "muted",
        },
    )
