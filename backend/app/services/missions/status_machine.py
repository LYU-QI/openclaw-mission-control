"""Mission and subtask lifecycle constants plus transition guards."""

from __future__ import annotations

from typing import Final

MISSION_STATUS_PENDING: Final = "pending"
MISSION_STATUS_DISPATCHED: Final = "dispatched"
MISSION_STATUS_RUNNING: Final = "running"
MISSION_STATUS_AGGREGATING: Final = "aggregating"
MISSION_STATUS_COMPLETED: Final = "completed"
MISSION_STATUS_FAILED: Final = "failed"
MISSION_STATUS_PENDING_APPROVAL: Final = "pending_approval"
MISSION_STATUS_CANCELLED: Final = "cancelled"

MISSION_STATUSES: Final[tuple[str, ...]] = (
    MISSION_STATUS_PENDING,
    MISSION_STATUS_DISPATCHED,
    MISSION_STATUS_RUNNING,
    MISSION_STATUS_AGGREGATING,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_FAILED,
    MISSION_STATUS_PENDING_APPROVAL,
    MISSION_STATUS_CANCELLED,
)

MISSION_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {MISSION_STATUS_COMPLETED, MISSION_STATUS_FAILED, MISSION_STATUS_CANCELLED}
)

SUBTASK_STATUS_PENDING: Final = "pending"
SUBTASK_STATUS_RUNNING: Final = "running"
SUBTASK_STATUS_COMPLETED: Final = "completed"
SUBTASK_STATUS_FAILED: Final = "failed"

SUBTASK_STATUSES: Final[tuple[str, ...]] = (
    SUBTASK_STATUS_PENDING,
    SUBTASK_STATUS_RUNNING,
    SUBTASK_STATUS_COMPLETED,
    SUBTASK_STATUS_FAILED,
)

SUBTASK_TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {SUBTASK_STATUS_COMPLETED, SUBTASK_STATUS_FAILED}
)

MISSION_ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    MISSION_STATUS_PENDING: frozenset(
        {MISSION_STATUS_DISPATCHED, MISSION_STATUS_PENDING_APPROVAL, MISSION_STATUS_CANCELLED}
    ),
    MISSION_STATUS_DISPATCHED: frozenset(
        {
            MISSION_STATUS_RUNNING,
            MISSION_STATUS_AGGREGATING,
            MISSION_STATUS_COMPLETED,
            MISSION_STATUS_FAILED,
            MISSION_STATUS_PENDING_APPROVAL,
            MISSION_STATUS_CANCELLED,
        }
    ),
    MISSION_STATUS_RUNNING: frozenset(
        {
            MISSION_STATUS_AGGREGATING,
            MISSION_STATUS_COMPLETED,
            MISSION_STATUS_FAILED,
            MISSION_STATUS_PENDING_APPROVAL,
            MISSION_STATUS_CANCELLED,
        }
    ),
    MISSION_STATUS_AGGREGATING: frozenset(
        {MISSION_STATUS_COMPLETED, MISSION_STATUS_FAILED, MISSION_STATUS_PENDING_APPROVAL}
    ),
    MISSION_STATUS_PENDING_APPROVAL: frozenset(
        {
            MISSION_STATUS_PENDING,
            MISSION_STATUS_RUNNING,
            MISSION_STATUS_COMPLETED,
            MISSION_STATUS_FAILED,
            MISSION_STATUS_CANCELLED,
        }
    ),
    MISSION_STATUS_COMPLETED: frozenset(),
    MISSION_STATUS_FAILED: frozenset({MISSION_STATUS_DISPATCHED, MISSION_STATUS_RUNNING}),
    MISSION_STATUS_CANCELLED: frozenset(),
}

SUBTASK_ALLOWED_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    SUBTASK_STATUS_PENDING: frozenset(
        {SUBTASK_STATUS_RUNNING, SUBTASK_STATUS_COMPLETED, SUBTASK_STATUS_FAILED}
    ),
    SUBTASK_STATUS_RUNNING: frozenset({SUBTASK_STATUS_COMPLETED, SUBTASK_STATUS_FAILED}),
    SUBTASK_STATUS_COMPLETED: frozenset(),
    SUBTASK_STATUS_FAILED: frozenset({SUBTASK_STATUS_PENDING, SUBTASK_STATUS_RUNNING}),
}


def ensure_known_mission_status(status: str) -> str:
    if status not in MISSION_STATUSES:
        raise ValueError(f"Unknown mission status '{status}'")
    return status


def ensure_known_subtask_status(status: str) -> str:
    if status not in SUBTASK_STATUSES:
        raise ValueError(f"Unknown subtask status '{status}'")
    return status


def ensure_mission_transition(current: str, target: str) -> None:
    ensure_known_mission_status(current)
    ensure_known_mission_status(target)
    if current == target:
        return
    if target not in MISSION_ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid mission transition: {current} -> {target}")


def ensure_subtask_transition(current: str, target: str) -> None:
    ensure_known_subtask_status(current)
    ensure_known_subtask_status(target)
    if current == target:
        return
    if target not in SUBTASK_ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid subtask transition: {current} -> {target}")
