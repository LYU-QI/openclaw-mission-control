# ruff: noqa: INP001, S101
"""Regression tests for board-group snapshot API boundary behavior."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.api import board_groups
from app.models.board_groups import BoardGroup


@dataclass
class _FakeSession:
    committed: int = 0

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_get_board_group_snapshot_rejects_negative_limit_without_building_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    group_id = uuid4()
    group = BoardGroup(id=group_id, organization_id=uuid4(), name="group", slug="group")

    async def _fake_require_group_access(*_args: object, **_kwargs: object) -> BoardGroup:
        return group

    build_called = False

    async def _fake_build_group_snapshot(*_args: object, **_kwargs: object) -> object:
        nonlocal build_called
        build_called = True
        raise AssertionError("build_group_snapshot should not be called for negative limits")

    monkeypatch.setattr(board_groups, "_require_group_access", _fake_require_group_access)
    monkeypatch.setattr(board_groups, "build_group_snapshot", _fake_build_group_snapshot)

    session: Any = _FakeSession()
    ctx = SimpleNamespace(member=SimpleNamespace())

    with pytest.raises(HTTPException) as exc_info:
        await board_groups.get_board_group_snapshot(
            group_id=group_id,
            per_board_task_limit=-1,
            session=session,
            ctx=ctx,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert build_called is False
