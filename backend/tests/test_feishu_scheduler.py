# ruff: noqa: INP001
"""Tests for periodic Feishu sync scheduling behavior."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.models.feishu_sync import FeishuSyncConfig
from app.services.feishu.scheduler import schedule_feishu_sync


class _FakeExecResult:
    def __init__(self, rows: list[FeishuSyncConfig]) -> None:
        self._rows = rows

    def all(self) -> list[FeishuSyncConfig]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[FeishuSyncConfig]) -> None:
        self._rows = rows

    async def exec(self, stmt: object) -> _FakeExecResult:
        del stmt
        return _FakeExecResult(self._rows)


def _build_config(
    *, minutes_since_sync: int | None, interval_minutes: int = 15
) -> FeishuSyncConfig:
    return FeishuSyncConfig(
        organization_id=uuid4(),
        board_id=uuid4(),
        app_id="app",
        app_secret_encrypted="enc::dummy",
        bitable_app_token="token",
        bitable_table_id="table",
        field_mapping={"title": "title"},
        sync_interval_minutes=interval_minutes,
        last_sync_at=(
            None if minutes_since_sync is None else utcnow() - timedelta(minutes=minutes_since_sync)
        ),
        enabled=True,
    )


def test_schedule_feishu_sync_enqueues_due_configs(monkeypatch: pytest.MonkeyPatch) -> None:
    due = _build_config(minutes_since_sync=20, interval_minutes=15)
    not_due = _build_config(minutes_since_sync=2, interval_minutes=15)
    session = _FakeSession([due, not_due])
    enqueued_payloads: list[dict[str, str]] = []

    def _fake_enqueue(task: object, queue_name: str, *, redis_url: str | None = None) -> bool:
        del queue_name, redis_url
        payload = getattr(task, "payload")
        enqueued_payloads.append(payload)
        return True

    monkeypatch.setattr("app.services.feishu.scheduler.enqueue_task", _fake_enqueue)

    queued = asyncio.run(schedule_feishu_sync(session))  # type: ignore[arg-type]

    assert queued == 1
    assert enqueued_payloads == [{"config_id": str(due.id)}]


def test_schedule_feishu_sync_enqueues_never_synced_config(monkeypatch: pytest.MonkeyPatch) -> None:
    never_synced = _build_config(minutes_since_sync=None)
    session = _FakeSession([never_synced])
    queued_payloads: list[dict[str, str]] = []

    def _fake_enqueue(task: object, queue_name: str, *, redis_url: str | None = None) -> bool:
        del queue_name, redis_url
        queued_payloads.append(getattr(task, "payload"))
        return True

    monkeypatch.setattr("app.services.feishu.scheduler.enqueue_task", _fake_enqueue)

    queued = asyncio.run(schedule_feishu_sync(session))  # type: ignore[arg-type]

    assert queued == 1
    assert queued_payloads[0]["config_id"] == str(never_synced.id)
