"""Escalation policy helpers for mission notifications."""

from __future__ import annotations


def should_escalate(*, status: str, retries: int, max_retries: int) -> bool:
    """Return whether an event should trigger escalation."""
    if status in {"failed", "pending_approval"}:
        return True
    return retries >= max_retries and max_retries > 0
