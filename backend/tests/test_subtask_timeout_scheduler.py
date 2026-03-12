# ruff: noqa: INP001
"""Tests for periodic mission subtask timeout handling."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.time import utcnow
from app.models.missions import Mission, MissionSubtask
from app.services.missions.subtask_timeout import fail_timed_out_subtasks


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def test_fail_timed_out_subtasks_marks_old_running_subtask_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _run() -> None:
        engine = await _make_engine()
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                mission = Mission(
                    id=uuid4(),
                    task_id=uuid4(),
                    board_id=uuid4(),
                    goal="Timeout test mission",
                    approval_policy="auto",
                    status="running",
                )
                subtask = MissionSubtask(
                    id=uuid4(),
                    mission_id=mission.id,
                    label="Wait for callback",
                    status="running",
                    assigned_subagent_id="subtask:test",
                    updated_at=utcnow() - timedelta(minutes=90),
                )
                session.add(mission)
                session.add(subtask)
                await session.commit()

                monkeypatch.setattr("app.core.config.settings.mission_subtask_timeout_minutes", 30)
                count = await fail_timed_out_subtasks(session)
                assert count == 1

                refreshed_subtask = (
                    await session.exec(select(MissionSubtask).where(MissionSubtask.id == subtask.id))
                ).first()
                assert refreshed_subtask is not None
                assert refreshed_subtask.status == "failed"
                assert refreshed_subtask.error_message == "Subtask timed out waiting for callback."
                assert refreshed_subtask.result_risk == "high"
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_fail_timed_out_subtasks_ignores_recent_subtask(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        engine = await _make_engine()
        session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with session_maker() as session:
                mission = Mission(
                    id=uuid4(),
                    task_id=uuid4(),
                    board_id=uuid4(),
                    goal="Recent subtask test mission",
                    approval_policy="auto",
                    status="running",
                )
                subtask = MissionSubtask(
                    id=uuid4(),
                    mission_id=mission.id,
                    label="Still fresh",
                    status="running",
                    assigned_subagent_id="subtask:test",
                    updated_at=utcnow() - timedelta(minutes=5),
                )
                session.add(mission)
                session.add(subtask)
                await session.commit()

                monkeypatch.setattr("app.core.config.settings.mission_subtask_timeout_minutes", 30)
                count = await fail_timed_out_subtasks(session)
                assert count == 0

                refreshed_subtask = (
                    await session.exec(select(MissionSubtask).where(MissionSubtask.id == subtask.id))
                ).first()
                assert refreshed_subtask is not None
                assert refreshed_subtask.status == "running"
        finally:
            await engine.dispose()

    asyncio.run(_run())
