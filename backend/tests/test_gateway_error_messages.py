# ruff: noqa: S101
from __future__ import annotations

from app.services.openclaw.error_messages import (
    classify_gateway_error_message,
    normalize_gateway_error_message,
)


def test_normalize_gateway_error_message_prefixes_pairing_required() -> None:
    message = 'handshake failed: cause="pairing-required" reason:"not-paired"'

    assert normalize_gateway_error_message(message) == (
        "PAIRING_REQUIRED: Gateway requires device pairing approval. "
        "Approve the Mission Control device in Gateway Dashboard and retry."
    )


def test_normalize_gateway_error_message_prefixes_transport_error() -> None:
    assert normalize_gateway_error_message("did not receive a valid HTTP response") == (
        "TRANSPORT_ERROR: Gateway transport error. Verify the remote gateway URL, "
        "network reachability, and WebSocket availability."
    )


def test_normalize_gateway_error_message_prefixes_checkin_timeout() -> None:
    assert normalize_gateway_error_message(
        "Agent did not check in after wake; max wake attempts reached",
    ) == (
        "CHECKIN_TIMEOUT: Agent did not check in after wake. "
        "Verify the remote session starts correctly."
    )


def test_classify_gateway_error_message_detects_token_mismatch() -> None:
    info = classify_gateway_error_message("gateway token mismatch")

    assert info.code == "TOKEN_MISMATCH"
    assert "does not match" in info.message
