"""Conflict resolution policy for bidirectional Feishu sync."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SyncSideState:
    """State snapshot for one side of a synchronized record."""

    updated_at: datetime | None
    checksum: str | None


class ConflictResolver:
    """Resolves sync conflicts using deterministic policy."""

    def resolve(self, *, feishu: SyncSideState, mission_control: SyncSideState) -> str:
        """Return winner side: `feishu`, `mission_control`, or `none`."""
        if feishu.checksum and mission_control.checksum and feishu.checksum == mission_control.checksum:
            return "none"
        if feishu.updated_at and mission_control.updated_at:
            return "feishu" if feishu.updated_at >= mission_control.updated_at else "mission_control"
        if feishu.updated_at:
            return "feishu"
        if mission_control.updated_at:
            return "mission_control"
        return "none"

