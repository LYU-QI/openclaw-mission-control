from __future__ import annotations

from uuid import uuid4

import pytest

import app.services.openclaw.session_service as session_service_module
from app.schemas.gateway_api import GatewayResolveQuery
from app.services.openclaw.gateway_rpc import GatewayConfig, OpenClawGatewayError
from app.services.openclaw.session_service import GatewaySessionService


class _DummyUser:
    id = uuid4()


@pytest.mark.asyncio
async def test_get_status_returns_transport_layers_for_gateway_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewaySessionService(session=object())  # type: ignore[arg-type]

    async def _fake_resolve_gateway(
        *args: object, **kwargs: object
    ) -> tuple[None, GatewayConfig, None]:
        del args, kwargs
        return None, GatewayConfig(url="ws://gateway.example"), None

    async def _fake_check_gateway_version_compatibility(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OpenClawGatewayError("did not receive a valid HTTP response")

    monkeypatch.setattr(service, "resolve_gateway", _fake_resolve_gateway)
    monkeypatch.setattr(
        session_service_module,
        "check_gateway_version_compatibility",
        _fake_check_gateway_version_compatibility,
    )

    payload = await service.get_status(
        params=GatewayResolveQuery(gateway_url="ws://gateway.example"),
        organization_id=uuid4(),
        user=_DummyUser(),
    )

    assert payload.connected is False
    assert payload.layers is not None
    assert payload.layers.http_reachable.ok is False
    assert payload.layers.ws_handshake.ok is False
    assert payload.layers.rpc_ready.ok is False


@pytest.mark.asyncio
async def test_get_status_returns_rpc_and_checkin_layers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GatewaySessionService(session=object())  # type: ignore[arg-type]

    async def _fake_resolve_gateway(
        *args: object, **kwargs: object
    ) -> tuple[None, GatewayConfig, str]:
        del args, kwargs
        return None, GatewayConfig(url="ws://gateway.example"), "agent:main:main"

    class _Compat:
        compatible = True
        message = None

    async def _fake_check_gateway_version_compatibility(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return _Compat()

    async def _fake_openclaw_call(
        method: str, *, config: GatewayConfig, params: object = None
    ) -> object:
        del config, params
        assert method == "sessions.list"
        return {"sessions": [{"key": "agent:main:main"}]}

    async def _fake_ensure_session(*args: object, **kwargs: object) -> object:
        del args, kwargs
        return {"entry": {"key": "agent:main:main"}}

    monkeypatch.setattr(service, "resolve_gateway", _fake_resolve_gateway)
    monkeypatch.setattr(
        session_service_module,
        "check_gateway_version_compatibility",
        _fake_check_gateway_version_compatibility,
    )
    monkeypatch.setattr(session_service_module, "openclaw_call", _fake_openclaw_call)
    monkeypatch.setattr(session_service_module, "ensure_session", _fake_ensure_session)

    payload = await service.get_status(
        params=GatewayResolveQuery(gateway_url="ws://gateway.example"),
        organization_id=uuid4(),
        user=_DummyUser(),
    )

    assert payload.connected is True
    assert payload.layers is not None
    assert payload.layers.http_reachable.ok is True
    assert payload.layers.ws_handshake.ok is True
    assert payload.layers.rpc_ready.ok is True
    assert payload.layers.session_visible.ok is True
    assert payload.layers.main_agent_checkin.ok is True
