from app.schemas.gateways import GatewayCreate, GatewayUpdate


def test_gateway_create_trims_name_url_workspace_root() -> None:
    payload = GatewayCreate(
        name="  Local Gateway  ",
        url="  ws://localhost:8000/ws  ",
        workspace_root="  ~/.openclaw  ",
        token="  secret  ",
    )

    assert payload.name == "Local Gateway"
    assert payload.url == "ws://localhost:8000/ws"
    assert payload.workspace_root == "~/.openclaw"
    assert payload.token == "secret"


def test_gateway_update_trims_name_url_workspace_root() -> None:
    payload = GatewayUpdate(
        name="  Updated Gateway  ",
        url="  wss://example.com/ws  ",
        workspace_root="  /tmp/openclaw  ",
    )

    assert payload.name == "Updated Gateway"
    assert payload.url == "wss://example.com/ws"
    assert payload.workspace_root == "/tmp/openclaw"
