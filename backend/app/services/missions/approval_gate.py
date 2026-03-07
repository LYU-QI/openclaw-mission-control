"""Approval policy evaluation for mission lifecycle."""

from __future__ import annotations

from app.models.boards import Board
from app.models.tasks import Task


class ApprovalGate:
    """Computes approval policy for a mission."""

    def evaluate(self, *, board: Board | None, task: Task) -> str:
        if task.priority == "urgent":
            return "pre_approve"
        if board and board.require_review_before_done:
            return "post_review"
        return "auto"

