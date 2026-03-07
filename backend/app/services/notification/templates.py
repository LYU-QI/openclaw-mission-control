"""Notification message templates."""

from __future__ import annotations


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

