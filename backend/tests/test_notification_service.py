from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.notifications import NotificationConfig
from app.services.notification.notification_service import NotificationService


@pytest.mark.asyncio
async def test_send_feishu_bot_uses_structured_template(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_send_feishu_webhook(*, webhook_url: str, payload: dict, secret: str = "") -> dict:
        captured["webhook_url"] = webhook_url
        captured["payload"] = payload
        captured["secret"] = secret
        return {"code": 0}

    monkeypatch.setattr(
        "app.services.notification.notification_service.send_feishu_webhook",
        _fake_send_feishu_webhook,
    )

    service = NotificationService(session=AsyncMock())
    response = service._send_feishu_bot(
        {
            "webhook_url": "https://example.com/hook",
            "webhook_secret": "secret-1",
        },
        {
            "event_type": "approval_granted",
            "message": "Mission approval decision: approved",
            "mission_id": str(uuid4()),
            "approval_id": str(uuid4()),
        },
    )

    assert response == {"code": 0}
    assert captured["webhook_url"] == "https://example.com/hook"
    assert captured["secret"] == "secret-1"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["msg_type"] == "interactive"
    assert payload["card"]["header"]["title"]["content"] == "✅ 审批已通过"


@pytest.mark.asyncio
async def test_notify_filters_configs_and_records_logs() -> None:
    session = AsyncMock()
    config = NotificationConfig(
        organization_id=uuid4(),
        name="Feishu",
        channel_type="feishu_bot",
        channel_config={"webhook_url": "https://example.com/hook"},
        notify_on_events=["mission_completed"],
        enabled=True,
    )
    session.exec.return_value = SimpleNamespace(all=lambda: [config])

    service = NotificationService(session=session)
    service._dispatch = AsyncMock(return_value=AsyncMock())

    logs = await service.notify(
        organization_id=config.organization_id,
        board_id=None,
        event_type="mission_completed",
        message="done",
        extra={"mission_id": "m1"},
    )

    assert len(logs) == 1
    service._dispatch.assert_awaited_once()
    session.commit.assert_awaited()
