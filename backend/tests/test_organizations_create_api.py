# ruff: noqa: INP001, S101
"""Regression tests for organization create API boundary behavior."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException, status

from app.api import organizations


@dataclass
class _FakeSession:
    committed: int = 0

    async def exec(self, _statement: object) -> object:
        raise AssertionError("exec should not be called for blank names")

    def add(self, _value: object) -> None:
        raise AssertionError("add should not be called for blank names")

    async def flush(self) -> None:
        raise AssertionError("flush should not be called for blank names")

    async def commit(self) -> None:
        self.committed += 1


@pytest.mark.asyncio
async def test_create_organization_rejects_blank_name_without_commit() -> None:
    session: Any = _FakeSession()
    auth = SimpleNamespace(user=SimpleNamespace(id="user-1"))

    with pytest.raises(HTTPException) as exc_info:
        await organizations.create_organization(
            payload=SimpleNamespace(name="   "),
            session=session,
            auth=auth,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert session.committed == 0
