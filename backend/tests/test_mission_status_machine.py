from app.services.missions.status_machine import (
    MISSION_STATUS_AGGREGATING,
    MISSION_STATUS_COMPLETED,
    MISSION_STATUS_DISPATCHED,
    MISSION_STATUS_PENDING,
    MISSION_STATUS_PENDING_APPROVAL,
    SUBTASK_STATUS_COMPLETED,
    SUBTASK_STATUS_FAILED,
    SUBTASK_STATUS_PENDING,
    ensure_mission_transition,
    ensure_subtask_transition,
)


def test_mission_transition_allows_pending_to_dispatched() -> None:
    ensure_mission_transition(MISSION_STATUS_PENDING, MISSION_STATUS_DISPATCHED)


def test_mission_transition_allows_aggregating_to_pending_approval() -> None:
    ensure_mission_transition(MISSION_STATUS_AGGREGATING, MISSION_STATUS_PENDING_APPROVAL)


def test_mission_transition_allows_pending_to_pending_approval() -> None:
    ensure_mission_transition(MISSION_STATUS_PENDING, MISSION_STATUS_PENDING_APPROVAL)


def test_mission_transition_rejects_pending_to_completed() -> None:
    try:
        ensure_mission_transition(MISSION_STATUS_PENDING, MISSION_STATUS_COMPLETED)
    except ValueError as exc:
        assert "pending -> completed" in str(exc)
    else:
        raise AssertionError("expected invalid mission transition to fail")


def test_subtask_transition_allows_failed_to_pending_for_redispatch() -> None:
    ensure_subtask_transition(SUBTASK_STATUS_FAILED, SUBTASK_STATUS_PENDING)


def test_subtask_transition_allows_pending_to_completed_for_callback_shortcut() -> None:
    ensure_subtask_transition(SUBTASK_STATUS_PENDING, SUBTASK_STATUS_COMPLETED)
