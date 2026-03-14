# ruff: noqa: INP001
"""Unit tests for OpenClaw mission result aggregation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from app.models.missions import Mission
from app.services.openclaw.aggregator.aggregator import ResultAggregator


def test_aggregator_returns_completed_without_failures() -> None:
    mission = Mission(
        id=uuid4(),
        task_id=uuid4(),
        board_id=uuid4(),
        goal="Generate deployment summary",
        approval_policy="auto",
    )
    aggregator = ResultAggregator()
    result = asyncio.run(
        aggregator.aggregate(
            mission=mission,
            subtask_results=[
                {"label": "collect", "status": "completed"},
                {"label": "summarize", "status": "completed"},
            ],
        ),
    )
    assert result.anomalies == []
    assert "completed=2" in result.summary
    assert result.risk == "low"
    assert result.evidence["stats"]["completed"] == 2


def test_aggregator_keeps_output_structured_for_non_auto_policy() -> None:
    mission = Mission(
        id=uuid4(),
        task_id=uuid4(),
        board_id=uuid4(),
        goal="Investigate production incident",
        approval_policy="post_review",
    )
    aggregator = ResultAggregator()
    result = asyncio.run(
        aggregator.aggregate(
            mission=mission,
            subtask_results=[
                {"label": "collect", "status": "completed"},
                {"label": "validate", "status": "failed", "error_message": "timeout"},
            ],
        ),
    )
    assert len(result.anomalies) == 1
    assert result.risk == "high"
    assert "retry" in result.next_action.lower()
