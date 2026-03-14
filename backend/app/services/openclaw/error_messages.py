"""Normalization helpers for user-facing OpenClaw gateway lifecycle errors."""

from __future__ import annotations

import re
from dataclasses import dataclass

_MISSING_SCOPE_PATTERN = re.compile(
    r"missing\s+scope\s*:\s*(?P<scope>[A-Za-z0-9._:-]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class GatewayErrorInfo:
    code: str
    message: str


def classify_gateway_error_message(message: str) -> GatewayErrorInfo:
    """Return a stable code + user-facing message for common gateway failures."""
    raw_message = message.strip()
    if not raw_message:
        return GatewayErrorInfo(
            code="AUTH_FAILED",
            message="Gateway authentication failed. Verify gateway token and operator scopes.",
        )

    missing_scope = _MISSING_SCOPE_PATTERN.search(raw_message)
    if missing_scope is not None:
        scope = missing_scope.group("scope")
        return GatewayErrorInfo(
            code="MISSING_SCOPE",
            message=(
                f"Gateway token is missing required scope `{scope}`. "
                "Update the gateway token scopes and retry."
            ),
        )

    lowered = raw_message.lower()

    if "pairing-required" in lowered or "pairing required" in lowered or "not-paired" in lowered:
        return GatewayErrorInfo(
            code="PAIRING_REQUIRED",
            message=(
                "Gateway requires device pairing approval. "
                "Approve the Mission Control device in Gateway Dashboard and retry."
            ),
        )

    if "token mismatch" in lowered:
        return GatewayErrorInfo(
            code="TOKEN_MISMATCH",
            message="Gateway token does not match the remote gateway configuration.",
        )

    if "unauthorized" in lowered or "forbidden" in lowered:
        return GatewayErrorInfo(
            code="AUTH_FAILED",
            message="Gateway authentication failed. Verify gateway token and operator scopes.",
        )

    if (
        "did not receive a valid http response" in lowered
        or "connection refused" in lowered
        or "timed out" in lowered
        or "timeout" in lowered
        or "503" in lowered
        or "closed before connect" in lowered
    ):
        return GatewayErrorInfo(
            code="TRANSPORT_ERROR",
            message=(
                "Gateway transport error. Verify the remote gateway URL, network reachability, "
                "and WebSocket availability."
            ),
        )

    if "did not check in after wake" in lowered or "check in after wake" in lowered:
        return GatewayErrorInfo(
            code="CHECKIN_TIMEOUT",
            message="Agent did not check in after wake. Verify the remote session starts correctly.",
        )

    return GatewayErrorInfo(code="UNKNOWN_GATEWAY_ERROR", message=raw_message)


def normalize_gateway_error_message(message: str) -> str:
    """Return a stable user-facing gateway error string with a machine-friendly code prefix."""
    info = classify_gateway_error_message(message)
    return f"{info.code}: {info.message}"
