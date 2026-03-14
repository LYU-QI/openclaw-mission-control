"""Generate mission-level output from subtask results."""

from __future__ import annotations

from typing import Any


def _compute_risk(*, failed: int, high_risk: int, pending: int) -> str:
    if failed > 0 or high_risk > 0:
        return "high"
    if pending > 0:
        return "medium"
    return "low"


def _compute_next_action(*, failed: int, pending: int, approval_required: bool) -> str:
    if failed > 0:
        return "Review failed subtasks and retry the mission with corrected inputs."
    if approval_required:
        return "Await human review and approval before executing follow-up actions."
    if pending > 0:
        return "Complete remaining subtasks before final handoff."
    return "Proceed to delivery and close the task."


def generate_output(
    *, goal: str, results: list[dict[str, Any]], anomalies: list[str]
) -> dict[str, object]:
    """Build mission summary/risk/action/evidence from subtasks."""
    completed = sum(1 for item in results if str(item.get("status", "")).lower() == "completed")
    failed = sum(1 for item in results if str(item.get("status", "")).lower() == "failed")
    pending = sum(
        1 for item in results if str(item.get("status", "")).lower() in {"pending", "running"}
    )
    high_risk = sum(
        1 for item in results if str(item.get("result_risk", "")).lower() in {"high", "critical"}
    )
    total = len(results)
    summary = (
        f"{goal[:140]} | subtasks total={total}, completed={completed}, "
        f"pending={pending}, failed={failed}, anomalies={len(anomalies)}"
    )
    risk = _compute_risk(failed=failed, high_risk=high_risk, pending=pending)
    next_action = _compute_next_action(
        failed=failed,
        pending=pending,
        approval_required=bool(anomalies and failed == 0),
    )
    evidence = {
        "subtask_results": results,
        "stats": {
            "total": total,
            "completed": completed,
            "pending": pending,
            "failed": failed,
            "high_risk": high_risk,
        },
        "anomalies": anomalies,
    }
    return {
        "summary": summary,
        "risk": risk,
        "next_action": next_action,
        "evidence": evidence,
    }
