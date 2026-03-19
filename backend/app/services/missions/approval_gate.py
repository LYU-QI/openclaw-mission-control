"""Approval policy evaluation for mission lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.boards import Board
from app.models.missions import Mission
from app.models.tasks import Task
from app.services.openclaw.aggregator.aggregator import AggregatedResult

ApprovalPolicy = Literal["auto", "pre_approve", "post_review"]


@dataclass(slots=True, frozen=True)
class ApprovalPolicyDecision:
    """Resolved approval policy for a mission."""

    policy: ApprovalPolicy
    reason: str
    requires_pre_dispatch_review: bool
    requires_result_review: bool


@dataclass(slots=True, frozen=True)
class MissionApprovalDecision:
    """Final approval decision after mission aggregation."""

    status: Literal["completed", "pending_approval"]
    approval_required: bool
    reason: str
    auditor_decision: dict[str, Any] | None = None  # LLM audit result if available


class ApprovalGate:
    """Computes approval policy and result-review requirements for a mission."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def resolve_policy(
        self,
        *,
        board: Board | None,
        task: Task,
        requested_policy: ApprovalPolicy = "auto",
    ) -> ApprovalPolicyDecision:
        if requested_policy != "auto":
            return self._decision_for_policy(
                requested_policy,
                reason=f"Mission requested explicit approval policy '{requested_policy}'.",
            )
        if task.priority == "urgent":
            return self._decision_for_policy(
                "pre_approve",
                reason="Urgent tasks require approval before dispatch.",
            )
        if board and board.require_review_before_done:
            return self._decision_for_policy(
                "post_review",
                reason="Board requires review before finalization.",
            )

        return self._decision_for_policy(
            "auto",
            reason="No board or task rule requires explicit mission approval.",
        )

    async def evaluate_result(
        self,
        *,
        mission: Mission,
        aggregated: AggregatedResult,
        task_title: str | None = None,
    ) -> MissionApprovalDecision:
        # Try Lead Auditor for intelligent evaluation when post_review policy is set
        auditor_decision = None
        if mission.approval_policy == "post_review":
            from app.services.openclaw.lead_auditor import LeadAuditor

            auditor = LeadAuditor()
            if auditor.is_enabled() and task_title:
                audit_result = await auditor.audit(
                    mission=mission,
                    task_title=task_title,
                    aggregated=aggregated,
                )
                if audit_result:
                    auditor_decision = {
                        "decision": audit_result.decision,
                        "summary": audit_result.summary,
                        "reason": audit_result.reason,
                        "suggestions": audit_result.suggestions,
                        "risk_confirmed": audit_result.risk_confirmed,
                        "missing_items": audit_result.missing_items,
                    }
                    # Use LLM audit decision - always request approval for post_review policy
                    # so humans can see what was approved
                    if audit_result.decision == "request_changes":
                        reason = f"[LLM Audit] {audit_result.reason}"
                        if audit_result.suggestions:
                            reason += "\n\nSuggestions:\n" + "\n".join(
                                f"- {s}" for s in audit_result.suggestions
                            )
                        return MissionApprovalDecision(
                            status="pending_approval",
                            approval_required=True,
                            reason=reason,
                            auditor_decision=auditor_decision,
                        )
                    else:
                        # Lead Auditor approved - still create approval for visibility/traceability
                        return MissionApprovalDecision(
                            status="pending_approval",
                            approval_required=True,
                            reason=f"[LLM Audit Approved] {audit_result.summary or 'Lead Auditor approved the results'}",
                            auditor_decision=auditor_decision,
                        )

        # Default policy check - post_review always needs approval for visibility
        if mission.approval_policy == "post_review":
            if aggregated.anomalies:
                return MissionApprovalDecision(
                    status="pending_approval",
                    approval_required=True,
                    reason="Mission produced anomalies under post-review policy.",
                    auditor_decision=auditor_decision,
                )
            # Even without anomalies, post_review policy requires approval for human visibility
            return MissionApprovalDecision(
                status="pending_approval",
                approval_required=True,
                reason="Post-review policy: mission completed, requires human acknowledgment.",
                auditor_decision=auditor_decision,
            )

        # Check dynamic rules from DB if session is available
        if self.session and mission.board_id:
            from sqlmodel import select

            from app.models.approval_rules import ApprovalRule
            from app.models.boards import Board

            board = await Board.objects.by_id(mission.board_id).first(self.session)
            if board:
                stmt = select(ApprovalRule).where(
                    ApprovalRule.organization_id == board.organization_id,
                    ApprovalRule.is_active == True,  # noqa: E712
                )
                rules = (await self.session.exec(stmt)).all()
                for rule in rules:
                    if rule.trigger_on_high_risk and aggregated.risk == "high":
                        return MissionApprovalDecision(
                            status="pending_approval",
                            approval_required=True,
                            reason=f"Triggered by rule '{rule.name}': High risk execution.",
                            auditor_decision=auditor_decision,
                        )
                    if (
                        rule.trigger_on_tool_usage
                        and aggregated.evidence
                        and "tools" in aggregated.evidence
                    ):
                        # Simple substring match for tool usage check as example
                        used_tools = str(aggregated.evidence["tools"])
                        for tool in rule.trigger_on_tool_usage.split(","):
                            if tool.strip() in used_tools:
                                return MissionApprovalDecision(
                                    status="pending_approval",
                                    approval_required=True,
                                    reason=f"Triggered by rule '{rule.name}': Sensitive tool used ({tool.strip()}).",
                                    auditor_decision=auditor_decision,
                                )

        return MissionApprovalDecision(
            status="completed",
            approval_required=False,
            reason="Mission does not require result review after aggregation.",
            auditor_decision=auditor_decision,
        )

    def _decision_for_policy(
        self, policy: ApprovalPolicy, *, reason: str
    ) -> ApprovalPolicyDecision:
        return ApprovalPolicyDecision(
            policy=policy,
            reason=reason,
            requires_pre_dispatch_review=policy == "pre_approve",
            requires_result_review=policy == "post_review",
        )
