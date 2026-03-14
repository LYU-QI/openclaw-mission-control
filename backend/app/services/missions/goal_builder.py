"""Build mission goals from task and board metadata."""

from __future__ import annotations

from app.models.boards import Board
from app.models.tasks import Task


class GoalBuilder:
    """Converts a board task into a mission goal statement."""

    def build(self, *, task: Task, board: Board | None) -> str:
        if task.description:
            return task.description
        if board and board.objective:
            return f"{task.title}. Objective: {board.objective}"
        return task.title
