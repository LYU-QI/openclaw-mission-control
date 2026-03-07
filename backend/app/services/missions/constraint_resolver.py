"""Mission execution constraint assembly."""

from __future__ import annotations

from typing import Any

from app.models.boards import Board


class ConstraintResolver:
    """Resolves runtime constraints from board policy."""

    def resolve(self, *, board: Board | None) -> dict[str, Any]:
        if board is None:
            return {}
        return {
            "require_approval_for_done": board.require_approval_for_done,
            "require_review_before_done": board.require_review_before_done,
            "only_lead_can_change_status": board.only_lead_can_change_status,
            "max_agents": board.max_agents,
        }

