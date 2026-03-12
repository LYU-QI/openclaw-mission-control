"""Stable identity helpers for mission subagent sessions."""

from __future__ import annotations

from uuid import UUID

from app.models.missions import MissionSubtask

_SUBAGENT_SESSION_PREFIX = "subtask:"


class MissionSubagentIdentity:
    """Build stable session ids and labels for mission subtasks."""

    @classmethod
    def session_key(cls, *, mission_id: UUID, subtask_id: UUID) -> str:
        return f"{_SUBAGENT_SESSION_PREFIX}{mission_id}:{subtask_id}"

    @staticmethod
    def label(subtask: MissionSubtask) -> str:
        return f"Subagent {subtask.order + 1}: {subtask.label}"
