import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.openclaw.gateway_rpc import GatewayConfig, OpenClawGatewayError, openclaw_call


@pytest.mark.asyncio
async def test_gateway_call_pairing_required_error(monkeypatch) -> None:
    config = GatewayConfig(url="ws://localhost:8080")

    challenge = json.dumps(
        {"type": "event", "event": "connect.challenge", "payload": {"nonce": "test-nonce"}}
    )

    class SmartMockWS:
        def __init__(self):
            self.sent = []
            self.challenge_sent = False

        async def recv(self):
            if not self.challenge_sent:
                self.challenge_sent = True
                return challenge

            while not self.sent:
                await asyncio.sleep(0.01)

            last_msg = json.loads(self.sent[-1])
            req_id = last_msg.get("id")

            return json.dumps(
                {
                    "type": "res",
                    "id": req_id,
                    "ok": False,
                    "error": {"message": "node pairing required"},
                }
            )

        async def send(self, data):
            self.sent.append(data)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("websockets.connect", lambda *a, **kw: SmartMockWS())

    with pytest.raises(OpenClawGatewayError) as exc:
        await openclaw_call("health", config=config)

    assert "pairing required" in str(exc.value)


@pytest.mark.asyncio
async def test_gateway_call_token_mismatch(monkeypatch) -> None:
    config = GatewayConfig(url="ws://localhost:8080", token="wrong-token")

    challenge = json.dumps(
        {"type": "event", "event": "connect.challenge", "payload": {"nonce": "test-nonce"}}
    )

    class SmartMockWS:
        def __init__(self):
            self.sent = []
            self.challenge_sent = False

        async def recv(self):
            if not self.challenge_sent:
                self.challenge_sent = True
                return challenge

            while not self.sent:
                await asyncio.sleep(0.01)

            last_msg = json.loads(self.sent[-1])
            req_id = last_msg.get("id")

            return json.dumps(
                {
                    "type": "res",
                    "id": req_id,
                    "ok": False,
                    "error": {"message": "invalid token or mismatch"},
                }
            )

        async def send(self, data):
            self.sent.append(data)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr("websockets.connect", lambda *a, **kw: SmartMockWS())

    with pytest.raises(OpenClawGatewayError) as exc:
        await openclaw_call("health", config=config)

    assert "token" in str(exc.value)


@pytest.mark.asyncio
async def test_gateway_call_network_timeout(monkeypatch) -> None:
    config = GatewayConfig(url="ws://localhost:8080")

    def mock_connect(*args, **kwargs):
        raise asyncio.TimeoutError("connection timed out")

    monkeypatch.setattr("websockets.connect", mock_connect)

    with pytest.raises(OpenClawGatewayError) as exc:
        await openclaw_call("health", config=config)

    assert "timed out" in str(exc.value)
