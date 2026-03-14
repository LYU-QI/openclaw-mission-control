# ruff: noqa: INP001
"""Unit tests for Feishu sync conflict resolution."""

from __future__ import annotations

from datetime import timedelta

from app.core.time import utcnow
from app.services.feishu.conflict_resolver import ConflictResolver, SyncSideState


def test_conflict_resolver_returns_none_when_checksums_match() -> None:
    resolver = ConflictResolver()
    now = utcnow()
    winner = resolver.resolve(
        feishu=SyncSideState(updated_at=now, checksum="abc"),
        mission_control=SyncSideState(updated_at=now + timedelta(seconds=30), checksum="abc"),
    )
    assert winner == "none"


def test_conflict_resolver_prefers_latest_timestamp() -> None:
    resolver = ConflictResolver()
    now = utcnow()
    winner = resolver.resolve(
        feishu=SyncSideState(updated_at=now, checksum="abc"),
        mission_control=SyncSideState(
            updated_at=now + timedelta(seconds=30),
            checksum="xyz",
        ),
    )
    assert winner == "mission_control"
