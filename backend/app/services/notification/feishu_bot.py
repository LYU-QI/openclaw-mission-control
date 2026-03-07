"""Feishu bot webhook sender."""

from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen


def send_feishu_webhook(*, webhook_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a webhook request to a Feishu bot endpoint."""
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read())

