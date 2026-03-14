from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlmodel import select

from app.models.boards import Board
from app.models.missions import Mission, MissionSubtask
from app.models.tasks import Task
from app.services.missions.orchestrator import MissionOrchestrator
from app.services.missions.status_machine import (
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_DISPATCHED,
    SUBTASK_STATUS_COMPLETED,
)


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
    added: list[Any] = field(default_factory=list)
    committed: int = 0
    refreshed: list[Any] = field(default_factory=list)
    deleted: list[Any] = field(default_factory=list)
    flushed: int = 0

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            return _FakeExecResult()
        return self.exec_results.pop(0)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed += 1

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, value: Any) -> None:
        self.refreshed.append(value)

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)


@pytest.mark.asyncio
async def test_mission_orchestration_full_flow(monkeypatch) -> None:
    # 准备基础数据
    org_id = uuid4()
    board = Board(id=uuid4(), organization_id=org_id, name="Test Board")
    task = Task(id=uuid4(), board_id=board.id, title="Test Task", status="inbox")

    # 构建 Mock Session。
    # 1. create_mission 需要查 Board, Task
    # 2. dispatch_mission 需要查 Mission, Board, Task...
    # 我们直接 Mock 掉 MissionOrchestrator 的数据访问部分更快捷，或者用 exec_results 喂数据。

    session: Any = _FakeSession(
        exec_results=[
            _FakeExecResult(first_value=board),  # create_mission -> Board lookup
            _FakeExecResult(first_value=task),  # create_mission -> Task lookup
            _FakeExecResult(first_value=board),  # create_mission -> notify -> Board lookup
        ]
    )

    orchestrator = MissionOrchestrator(session)
    # Mock 通知服务避免真实调用
    monkeypatch.setattr(orchestrator.notification_service, "notify", AsyncMock())

    # 1. Mock Decomposer (子任务分解)
    mock_subtask_specs = [
        SimpleNamespace(
            label="Step 1", description="D1", tool_scope=[], expected_output="O1", order=0
        ),
        SimpleNamespace(
            label="Step 2", description="D2", tool_scope=[], expected_output="O2", order=1
        ),
    ]
    monkeypatch.setattr(
        orchestrator.decomposer, "decompose", AsyncMock(return_value=mock_subtask_specs)
    )

    # 2. Mock SubagentDispatchService (网关派发)
    from app.services.openclaw.subagent_dispatch import SubagentDispatchService

    mock_dispatch = AsyncMock()
    monkeypatch.setattr(SubagentDispatchService, "dispatch_subtasks_for_mission", mock_dispatch)

    # 3. 创建 Mission
    mission = await orchestrator.create_mission(
        task_id=task.id, board_id=board.id, goal="达成测试目标", approval_policy="auto"
    )
    assert mission.status == "pending"

    # 4. 派发 Mission
    # 补充 dispatch_mission 需要的查询结果
    session.exec_results.extend(
        [
            _FakeExecResult(first_value=mission),  # dispatch_mission -> Mission lookup
            _FakeExecResult(all_values=[]),  # _ensure_subtasks_for_mission -> existing check
            _FakeExecResult(first_value=task),  # dispatch_mission -> Task lookup
            _FakeExecResult(first_value=board),  # dispatch_mission -> notify -> Board lookup
        ]
    )

    mission = await orchestrator.dispatch_mission(mission.id)
    assert mission.status == MISSION_STATUS_DISPATCHED
    assert mock_dispatch.called

    # 验证子任务是否已创建 (通过 session.added)
    subtasks = [it for it in session.added if isinstance(it, MissionSubtask)]
    assert len(subtasks) == 2
    assert subtasks[0].label == "Step 1"

    # 5. 模拟网关回调：完成第一个子任务
    session.exec_results.extend(
        [
            _FakeExecResult(first_value=subtasks[0]),  # update_subtask_status -> Subtask lookup
            _FakeExecResult(first_value=mission),  # update_subtask_status -> Mission lookup
            _FakeExecResult(all_values=[subtasks[0], subtasks[1]]),  # _all_subtasks_terminal
        ]
    )

    await orchestrator.update_subtask_status(
        subtasks[0].id, status=SUBTASK_STATUS_COMPLETED, result_summary="Step 1 done"
    )

    assert mission.status == MISSION_STATUS_DISPATCHED

    # 6. 模拟网关回调：完成第二个子任务
    session.exec_results.extend(
        [
            _FakeExecResult(first_value=subtasks[1]),  # update_subtask_status -> Subtask lookup
            _FakeExecResult(first_value=mission),  # update_subtask_status -> Mission lookup
            _FakeExecResult(
                all_values=[subtasks[0], subtasks[1]]
            ),  # update_subtask_status -> _all_subtasks_terminal
            # complete_mission 内部逻辑
            _FakeExecResult(first_value=mission),  # complete_mission -> Mission lookup
            _FakeExecResult(
                all_values=[subtasks[0], subtasks[1]]
            ),  # complete_mission -> subtask_rows check
            _FakeExecResult(first_value=task),  # complete_mission -> Task lookup
            _FakeExecResult(first_value=board),  # complete_mission -> notify -> Board lookup
        ]
    )

    # Mock Aggregator and ApprovalGate for simplicity
    monkeypatch.setattr(
        orchestrator.aggregator,
        "aggregate",
        AsyncMock(
            return_value=SimpleNamespace(summary="A", risk="low", evidence={}, next_action="N")
        ),
    )
    monkeypatch.setattr(
        orchestrator.approval_gate,
        "evaluate_result",
        AsyncMock(return_value=SimpleNamespace(status=MISSION_STATUS_COMPLETED)),
    )

    await orchestrator.update_subtask_status(
        subtasks[1].id, status=SUBTASK_STATUS_COMPLETED, result_summary="Step 2 done"
    )

    # 7. 验证最终状态
    assert mission.status == MISSION_STATUS_COMPLETED
    assert task.status == "review"
