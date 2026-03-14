"""Approval policy evaluation for mission lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
    ) -> MissionApprovalDecision:
        # Default policy check
        if mission.approval_policy == "post_review" and aggregated.anomalies:
            return MissionApprovalDecision(
                status="pending_approval",
                approval_required=True,
                reason="Mission produced anomalies under post-review policy.",
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
                                )

        return MissionApprovalDecision(
            status="completed",
            approval_required=False,
            reason="Mission does not require result review after aggregation.",
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
