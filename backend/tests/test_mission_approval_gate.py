from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.boards import Board
from app.models.missions import Mission
from app.models.tasks import Task
from app.services.missions.approval_gate import ApprovalGate
from app.services.openclaw.aggregator.aggregator import AggregatedResult


@pytest.mark.asyncio
async def test_resolve_policy_escalates_urgent_tasks_to_preapprove() -> None:
    gate = ApprovalGate()
    task = Task(id=uuid4(), board_id=uuid4(), title="Urgent task", priority="urgent")

    decision = await gate.resolve_policy(board=None, task=task, requested_policy="auto")

    assert decision.policy == "pre_approve"
    assert decision.requires_pre_dispatch_review is True
    assert decision.requires_result_review is False


@pytest.mark.asyncio
async def test_resolve_policy_uses_board_review_rule_for_auto_policy() -> None:
    gate = ApprovalGate()
    board = Board(id=uuid4(), name="Ops", organization_id=uuid4(), require_review_before_done=True)
    task = Task(id=uuid4(), board_id=board.id, title="Investigate issue", priority="medium")

    decision = await gate.resolve_policy(board=board, task=task, requested_policy="auto")

    assert decision.policy == "post_review"
    assert decision.requires_result_review is True
    assert decision.requires_pre_dispatch_review is False


@pytest.mark.asyncio
async def test_evaluate_result_requests_approval_for_post_review_anomalies() -> None:
    gate = ApprovalGate()
    mission = Mission(
        id=uuid4(),
        task_id=uuid4(),
        board_id=uuid4(),
        goal="Review risky result",
        approval_policy="post_review",
    )
    aggregated = AggregatedResult(
        summary="summary",
        risk="high",
        next_action="retry",
        evidence={},
        anomalies=["subtask failed"],
    )

    decision = await gate.evaluate_result(mission=mission, aggregated=aggregated)

    assert decision.status == "pending_approval"
    assert decision.approval_required is True


@pytest.mark.asyncio
async def test_evaluate_result_completes_preapprove_mission_after_execution() -> None:
    gate = ApprovalGate()
    mission = Mission(
        id=uuid4(),
        task_id=uuid4(),
        board_id=uuid4(),
        goal="Approved before dispatch",
        approval_policy="pre_approve",
    )
    aggregated = AggregatedResult(
        summary="summary",
        risk="low",
        next_action="done",
        evidence={},
        anomalies=[],
    )

    decision = await gate.evaluate_result(mission=mission, aggregated=aggregated)

    assert decision.status == "completed"
    assert decision.approval_required is False
