"""Validation for generated subtasks."""

from __future__ import annotations

from typing import Any


def _normalize_tool_scope(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
        deduped = list(dict.fromkeys(values))
        return deduped or ["analysis"]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return ["analysis"]


def validate_subtasks(items: list[dict[str, Any]], *, max_items: int = 10) -> list[dict[str, Any]]:
    """Drop malformed subtasks and normalize fields while preserving order."""
    output: list[dict[str, Any]] = []
    for item in items:
        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            continue
        description = item.get("description")
        expected_output = item.get("expected_output")
        normalized = {
            "label": label.strip()[:120],
            "description": (
                description.strip()[:500]
                if isinstance(description, str) and description.strip()
                else "No description provided."
            ),
            "tool_scope": _normalize_tool_scope(item.get("tool_scope")),
            "expected_output": (
                expected_output.strip()[:500]
                if isinstance(expected_output, str) and expected_output.strip()
                else "Structured analysis output."
            ),
        }
        output.append(normalized)
        if len(output) >= max_items:
            break
    return output
