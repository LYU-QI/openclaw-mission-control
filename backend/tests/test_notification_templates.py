from __future__ import annotations

from app.services.notification.templates import build_feishu_card_payload


def test_build_feishu_card_payload_for_mission_completion() -> None:
    payload = build_feishu_card_payload(
        event_type="mission_completed",
        message="Mission completed successfully",
        payload={
            "mission_id": "mission-1",
            "task_id": "task-1",
            "risk": "low",
            "next_action": "Notify stakeholder",
        },
    )

    assert payload["msg_type"] == "interactive"
    card = payload["card"]
    assert isinstance(card, dict)
    assert card["header"]["title"]["content"] == "✅ 任务执行完成"
    assert card["header"]["template"] == "green"
    context = card["elements"][1]["text"]["content"]
    assert "**Mission**: `mission-1`" in context
    assert "**Task**: `task-1`" in context
    assert "**风险**: low" in context
    assert "**下一步**: Notify stakeholder" in context


def test_build_feishu_card_payload_for_approval_request() -> None:
    payload = build_feishu_card_payload(
        event_type="approval_requested",
        message="Mission requires approval before dispatch",
        payload={
            "approval_id": "approval-1",
            "mission_id": "mission-2",
            "status": "pending_approval",
        },
    )

    card = payload["card"]
    assert card["header"]["title"]["content"] == "⚠️ 需要人工审批"
    assert card["header"]["template"] == "orange"
    context = card["elements"][1]["text"]["content"]
    assert "**Approval**: `approval-1`" in context
    assert "**Mission**: `mission-2`" in context
    assert "**状态**: pending_approval" in context
