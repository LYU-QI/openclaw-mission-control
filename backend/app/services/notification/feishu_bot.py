"""Feishu bot webhook sender."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.request import Request, urlopen


def _generate_signature(secret: str, timestamp: int) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_feishu_webhook(
    *,
    webhook_url: str,
    payload: dict[str, Any],
    secret: str = "",
) -> dict[str, Any]:
    """Send a webhook request to a Feishu bot endpoint."""
    request_payload = dict(payload)
    if secret.strip():
        timestamp = int(time.time())
        request_payload["timestamp"] = str(timestamp)
        request_payload["sign"] = _generate_signature(secret.strip(), timestamp)

    data = json.dumps(request_payload).encode("utf-8")
    req = Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=10) as resp:  # noqa: S310
        return json.loads(resp.read())
