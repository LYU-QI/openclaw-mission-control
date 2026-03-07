"""Aggregate mission subtask execution results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.missions import Mission
from app.services.openclaw.aggregator.anomaly_detector import detect_anomalies
from app.services.openclaw.aggregator.output_generator import generate_output


@dataclass(slots=True)
class AggregatedResult:
    """Final aggregated mission result."""

    status: str
    summary: str
    risk: str
    next_action: str
    evidence: dict[str, Any]
    anomalies: list[str]


class ResultAggregator:
    """Result aggregation and anomaly classification."""

    async def aggregate(
        self,
        *,
        mission: Mission,
        subtask_results: list[dict[str, Any]],
    ) -> AggregatedResult:
        anomalies = detect_anomalies(subtask_results)
        output = generate_output(goal=mission.goal, results=subtask_results, anomalies=anomalies)
        status = "pending_approval" if anomalies and mission.approval_policy != "auto" else "completed"
        return AggregatedResult(
            status=status,
            summary=str(output["summary"]),
            risk=str(output["risk"]),
            next_action=str(output["next_action"]),
            evidence=dict(output["evidence"]),
            anomalies=anomalies,
        )
