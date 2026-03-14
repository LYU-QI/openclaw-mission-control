"""Notification message templates."""

from __future__ import annotations

from typing import Any

EVENT_META: dict[str, dict[str, str]] = {
    "mission_created": {"title": "📋 新任务已创建", "template": "blue"},
    "mission_dispatched": {"title": "🚀 任务已下发", "template": "blue"},
    "mission_started": {"title": "⚡ 任务开始执行", "template": "blue"},
    "mission_completed": {"title": "✅ 任务执行完成", "template": "green"},
    "mission_failed": {"title": "❌ 任务执行失败", "template": "red"},
    "approval_requested": {"title": "⚠️ 需要人工审批", "template": "orange"},
    "approval_granted": {"title": "✅ 审批已通过", "template": "green"},
    "approval_rejected": {"title": "❌ 审批已拒绝", "template": "red"},
    "feishu_sync_pull": {"title": "🔄 飞书同步完成", "template": "blue"},
    "feishu_sync_push": {"title": "📤 结果已回写飞书", "template": "blue"},
    "test": {"title": "🔔 测试通知", "template": "blue"},
}


def _event_meta(event_type: str) -> dict[str, str]:
    return EVENT_META.get(event_type, {"title": f"📢 {event_type}", "template": "blue"})


def _string_field(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _build_context_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for label, key in (
        ("Mission", "mission_id"),
        ("Task", "task_id"),
        ("Board", "board_id"),
        ("Approval", "approval_id"),
    ):
        value = _string_field(payload, key)
        if value:
            lines.append(f"**{label}**: `{value}`")

    status = _string_field(payload, "status")
    if status:
        lines.append(f"**状态**: {status}")

    risk = _string_field(payload, "risk")
    if risk:
        lines.append(f"**风险**: {risk}")

    next_action = _string_field(payload, "next_action")
    if next_action:
        lines.append(f"**下一步**: {next_action}")

    return lines


def build_feishu_card_payload(
    *,
    event_type: str,
    message: str,
    payload: dict[str, Any],
) -> dict[str, object]:
    """Build a structured Feishu interactive card payload."""
    meta = _event_meta(event_type)
    elements: list[dict[str, object]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": message,
            },
        }
    ]

    context_lines = _build_context_lines(payload)
    if context_lines:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": "\n".join(context_lines),
                },
            }
        )

    error_msg = (
        _string_field(payload, "error_message")
        or _string_field(payload, "failure_reason")
        or _string_field(payload, "error")
    )
    if error_msg:
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**❌ 错误详情**:\n<font color='red'>{error_msg}</font>",
                },
            }
        )

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": meta["title"]},
                "template": meta["template"],
            },
            "elements": elements,
        },
    }


def mission_progress_card(*, title: str, status: str, detail: str) -> dict[str, object]:
    """Build a Feishu interactive card payload."""
    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": f"**状态**: {status}"}},
                {"tag": "div", "text": {"tag": "lark_md", "content": detail}},
            ],
        },
    }
