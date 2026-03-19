"""Lead Auditor for intelligent mission result evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.models.missions import Mission
from app.services.openclaw.aggregator.aggregator import AggregatedResult
from app.services.openclaw.lead_auditor.templates import build_audit_prompt
from app.services.openclaw.llm_client import LLMClient


@dataclass(slots=True)
class AuditorDecision:
    """Result of Lead Auditor's evaluation."""

    decision: Literal["approve", "request_changes"]
    summary: str
    reason: str
    suggestions: list[str]
    risk_confirmed: bool
    missing_items: list[str]


class LeadAuditor:
    """Intelligent Lead Agent for auditing mission results using LLM."""

    def __init__(self) -> None:
        self._llm_client = LLMClient(temperature=0.3)

    def is_enabled(self) -> bool:
        """Check if Lead Auditor is properly configured."""
        return self._llm_client.is_enabled()

    async def audit(
        self,
        *,
        mission: Mission,
        task_title: str,
        aggregated: AggregatedResult,
    ) -> AuditorDecision | None:
        """Audit mission results using LLM.

        Args:
            mission: The mission that was executed
            task_title: Title of the parent task
            aggregated: Aggregated result from subtask execution

        Returns:
            AuditorDecision if audit was performed, None if LLM is not available
        """
        if not self.is_enabled():
            return None

        # Extract subtask results from evidence
        subtask_results = []
        evidence = aggregated.evidence or {}
        if "subtask_results" in evidence:
            subtask_results = evidence["subtask_results"] or []

        # Build and send audit prompt
        prompt = build_audit_prompt(
            mission_goal=mission.goal,
            task_title=task_title,
            result_summary=aggregated.summary,
            result_risk=aggregated.risk,
            result_next_action=aggregated.next_action,
            subtask_results=subtask_results,
            anomalies=aggregated.anomalies,
        )

        try:
            result = await self._llm_client.request_json(prompt)
            return self._parse_audit_result(result)
        except Exception as e:
            # Log error but don't fail the mission
            import logging

            logging.warning(f"Lead Auditor failed: {e}")
            return None

    def _parse_audit_result(self, result: dict[str, Any]) -> AuditorDecision:
        """Parse LLM response into AuditorDecision."""
        decision = result.get("decision", "approve")
        if decision not in ("approve", "request_changes"):
            decision = "approve"

        return AuditorDecision(
            decision=decision,
            summary=str(result.get("summary", "")),
            reason=str(result.get("reason", "")),
            suggestions=list(result.get("suggestions", [])),
            risk_confirmed=bool(result.get("risk_confirmed", True)),
            missing_items=list(result.get("missing_items", [])),
        )
