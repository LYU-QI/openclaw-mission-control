"""Anomaly detection for subtask outputs."""

from __future__ import annotations

from typing import Any


def detect_anomalies(results: list[dict[str, Any]]) -> list[str]:
    """Return anomaly descriptions detected in subtask outputs."""
    anomalies: list[str] = []
    for item in results:
        label = str(item.get("label", "unknown"))
        status = str(item.get("status", "")).lower()
        if status == "failed":
            reason = item.get("error_message") or item.get("result_risk") or "unspecified error"
            anomalies.append(f"Subtask failed: {label} ({reason})")
        elif status not in {"completed", "failed", "pending", "running"}:
            anomalies.append(f"Unexpected subtask status: {label} -> {status}")

        risk = str(item.get("result_risk", "")).lower()
        if risk in {"high", "critical"}:
            anomalies.append(f"High risk flagged by subtask: {label} ({risk})")
    return anomalies
