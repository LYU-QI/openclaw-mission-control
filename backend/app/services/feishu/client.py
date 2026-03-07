"""Feishu Open Platform API client for Bitable and messaging operations."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"
TOKEN_URL = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"


class FeishuClient:
    """Lightweight HTTP client for the Feishu Open Platform REST API."""

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _get_tenant_access_token(self) -> str:
        """Obtain (or reuse) a tenant access token from the Feishu API."""
        if self._token:
            return self._token
        payload = json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode()
        req = Request(TOKEN_URL, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read())
        if data.get("code") != 0:
            raise RuntimeError(f"Failed to get tenant_access_token: {data}")
        self._token = data["tenant_access_token"]
        return self._token  # type: ignore[return-value]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_tenant_access_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=self._headers(), method=method)
        with urlopen(req, timeout=30) as resp:  # noqa: S310
            result: dict[str, Any] = json.loads(resp.read())
        if result.get("code") != 0:
            logger.error("Feishu API error: %s", result)
        return result

    # ------------------------------------------------------------------
    # Bitable (Multi-dimensional table) operations
    # ------------------------------------------------------------------

    def list_bitable_records(
        self,
        app_token: str,
        table_id: str,
        *,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict[str, Any]:
        """List records from a Feishu Bitable table."""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        params = [f"page_size={page_size}"]
        if page_token:
            params.append(f"page_token={page_token}")
        url = f"{url}?{'&'.join(params)}"
        return self._request("GET", url)

    def get_bitable_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict[str, Any]:
        """Retrieve a single Bitable record by ID."""
        url = (
            f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/records/{record_id}"
        )
        return self._request("GET", url)

    def create_bitable_record(
        self,
        app_token: str,
        table_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new record in a Bitable table."""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        return self._request("POST", url, body={"fields": fields})

    def update_bitable_record(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Update an existing Bitable record."""
        url = (
            f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}"
            f"/tables/{table_id}/records/{record_id}"
        )
        return self._request("PUT", url, body={"fields": fields})

    # ------------------------------------------------------------------
    # Bot messaging
    # ------------------------------------------------------------------

    def send_bot_message(
        self,
        webhook_url: str,
        msg_type: str,
        content: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a message to a Feishu group via bot webhook."""
        payload = {"msg_type": msg_type, "content": content}
        data = json.dumps(payload).encode()
        req = Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            result: dict[str, Any] = json.loads(resp.read())
        return result

    def invalidate_token(self) -> None:
        """Clear cached token to force re-authentication."""
        self._token = None
