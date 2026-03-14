from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.time import utcnow
from app.models.approvals import Approval
from app.models.boards import Board
from app.models.missions import Mission, MissionSubtask
from app.services.watcher.attention import AttentionCollector


@dataclass
class _FakeExecResult:
    first_value: Any = None
    all_values: list[Any] | None = None

    def first(self) -> Any:
        return self.first_value

    def all(self) -> list[Any]:
        return self.all_values or []

    def __iter__(self):
        return iter(self.all_values or [])


@dataclass
class _FakeSession:
    exec_results: list[Any] = field(default_factory=list)

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            return _FakeExecResult()
        return self.exec_results.pop(0)


@pytest.mark.asyncio
async def test_attention_collector_aggregates_all_types(monkeypatch) -> None:
    board_id = uuid4()
    board = Board(id=board_id, name="Test Board")

    # 1. Failed Subtask
    mission_a = Mission(id=uuid4(), board_id=board_id, goal="Goal A", status="running")
    subtask_f = MissionSubtask(
        id=uuid4(),
        mission_id=mission_a.id,
        label="Failed Task",
        status="failed",
        error_message="Crash",
        updated_at=utcnow(),
    )

    # 2. Timed out Subtask
    mission_b = Mission(id=uuid4(), board_id=board_id, goal="Goal B", status="running")
    timeout_cutoff = utcnow() - timedelta(minutes=settings.mission_subtask_timeout_minutes + 1)
    subtask_t = MissionSubtask(
        id=uuid4(),
        mission_id=mission_b.id,
        label="Timed Out Task",
        status="running",
        updated_at=timeout_cutoff,
    )

    # 3. Stale Mission
    stale_cutoff = utcnow() - timedelta(hours=3)
    mission_s = Mission(
        id=uuid4(),
        board_id=board_id,
        goal="Stale Mission",
        status="running",
        updated_at=stale_cutoff,
    )

    # 4. Pending Approval
    approval_p = Approval(
        id=uuid4(),
        board_id=board_id,
        status="pending",
        action_type="test_action",
        confidence=0.85,
        created_at=utcnow(),
    )

    # Mock Session with results in the order Collector calls them:
    # 1. _failed_subtasks
    # 2. _timed_out_subtasks
    # 3. _stale_missions
    # 4. _pending_approvals
    session = _FakeSession(
        exec_results=[
            _FakeExecResult(all_values=[(subtask_f, mission_a, board)]),
            _FakeExecResult(all_values=[(subtask_t, mission_b, board)]),
            _FakeExecResult(all_values=[(mission_s, board)]),
            _FakeExecResult(all_values=[(approval_p, board)]),
        ]
    )

    collector = AttentionCollector(session)
    snapshot = await collector.collect(board_ids=[board_id])

    assert snapshot.total == 4
    assert snapshot.failed_subtasks == 1
    assert snapshot.timed_out_subtasks == 1
    assert snapshot.stale_missions == 1
    assert snapshot.pending_approvals == 1

    # 验证排序与内容
    # Severity order: failed(critical) > timed_out(warning) > stale(warning) > approval(info)
    assert snapshot.items[0].category == "failed_subtask"
    assert snapshot.items[0].severity == "critical"

    # 验证超时子任务的识别
    timeout_item = next(it for it in snapshot.items if it.category == "timed_out_subtask")
    assert "超时" in timeout_item.title

    # 验证停滞 Mission 的识别
    stale_item = next(it for it in snapshot.items if it.category == "stale_mission")
    assert "停滞" in stale_item.title


@pytest.mark.asyncio
async def test_attention_collector_empty_boards() -> None:
    session = _FakeSession()
    collector = AttentionCollector(session)
    snapshot = await collector.collect(board_ids=[])
    assert snapshot.total == 0
    assert snapshot.items == []
