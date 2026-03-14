# ruff: noqa: INP001
"""E2E-style integration tests for Feishu sync, mission lifecycle and notification flows."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.approvals import router as approvals_router
from app.api.feishu_sync import router as feishu_sync_router
from app.api.missions import router as missions_router
from app.api.notifications import router as notifications_router
from app.core.auth import AuthContext, get_auth_context
from app.db.session import get_session
from app.models.activity_events import ActivityEvent
from app.models.approvals import Approval
from app.models.boards import Board
from app.models.feishu_sync import FeishuTaskMapping
from app.models.missions import MissionSubtask
from app.models.notifications import NotificationLog
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.tasks import Task
from app.models.users import User
from app.services.feishu.client import FeishuClient


@dataclass(frozen=True)
class _TestContext:
    engine: AsyncEngine
    session_maker: async_sessionmaker[AsyncSession]
    app: FastAPI
    org_id: UUID
    board_id: UUID


async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


def _build_test_app(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    user: User,
) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(feishu_sync_router)
    api_v1.include_router(missions_router)
    api_v1.include_router(notifications_router)
    api_v1.include_router(approvals_router)
    app.include_router(api_v1)

    async def _override_get_session() -> AsyncSession:
        async with session_maker() as session:
            yield session

    async def _override_get_auth_context() -> AuthContext:
        return AuthContext(actor_type="user", user=user)

    app.dependency_overrides[get_session] = _override_get_session
    app.dependency_overrides[get_auth_context] = _override_get_auth_context
    return app


def _patch_feishu_client(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_list_bitable_records(
        self: FeishuClient,
        app_token: str,
        table_id: str,
        *,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict:
        del self, app_token, table_id, page_size, page_token
        return {
            "code": 0,
            "data": {
                "items": [
                    {
                        "record_id": "rec-e2e-1",
                        "fields": {
                            "title_col": "E2E synced task",
                            "desc_col": "Task created from Feishu",
                            "priority_col": "high",
                            "status_col": "todo",
                        },
                    },
                ],
                "has_more": False,
            },
        }

    def _fake_update_bitable_record(
        self: FeishuClient,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: dict,
    ) -> dict:
        del self, app_token, table_id, record_id, fields
        return {"code": 0}

    def _fake_get_bitable_record(
        self: FeishuClient,
        app_token: str,
        table_id: str,
        record_id: str,
    ) -> dict:
        del self, app_token, table_id, record_id
        return {
            "code": 0,
            "data": {
                "record": {
                    "fields": {
                        "title_col": "E2E synced task",
                        "desc_col": "Task created from Feishu",
                        "priority_col": "high",
                        "status_col": "todo",
                    },
                },
            },
        }

    monkeypatch.setattr(FeishuClient, "list_bitable_records", _fake_list_bitable_records)
    monkeypatch.setattr(FeishuClient, "update_bitable_record", _fake_update_bitable_record)
    monkeypatch.setattr(FeishuClient, "get_bitable_record", _fake_get_bitable_record)


async def _bootstrap(monkeypatch: pytest.MonkeyPatch) -> _TestContext:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        org = Organization(id=uuid4(), name="E2E Org")
        user = User(
            id=uuid4(),
            clerk_user_id="local-auth-user",
            email="admin@home.local",
            name="Local User",
            active_organization_id=org.id,
        )
        board = Board(
            id=uuid4(),
            organization_id=org.id,
            name="E2E Board",
            slug="e2e-board",
        )
        member = OrganizationMember(
            id=uuid4(),
            organization_id=org.id,
            user_id=user.id,
            role="owner",
            all_boards_read=True,
            all_boards_write=True,
        )
        session.add(org)
        session.add(user)
        session.add(board)
        session.add(member)
        await session.commit()
        await session.refresh(user)

    _patch_feishu_client(monkeypatch)
    app = _build_test_app(session_maker, user=user)
    return _TestContext(
        engine=engine,
        session_maker=session_maker,
        app=app,
        org_id=org.id,
        board_id=board.id,
    )


async def _create_notification_config(client: AsyncClient, ctx: _TestContext) -> None:
    notification_resp = await client.post(
        "/api/v1/notifications/configs",
        json={
            "organization_id": str(ctx.org_id),
            "board_id": str(ctx.board_id),
            "channel_type": "feishu_bot",
            "channel_config": {},
            "notify_on_events": [
                "mission_created",
                "mission_dispatched",
                "mission_started",
                "mission_completed",
            ],
            "enabled": True,
        },
    )
    assert notification_resp.status_code == 201


async def _create_and_trigger_feishu_sync(client: AsyncClient, ctx: _TestContext) -> str:
    feishu_cfg_resp = await client.post(
        "/api/v1/feishu-sync/configs",
        json={
            "organization_id": str(ctx.org_id),
            "board_id": str(ctx.board_id),
            "app_id": "app_id",
            "app_secret": "app_secret",
            "bitable_app_token": "bitable_app_token",
            "bitable_table_id": "bitable_table_id",
            "field_mapping": {
                "title_col": "title",
                "desc_col": "description",
                "priority_col": "priority",
                "status_col": "status",
            },
        },
    )
    assert feishu_cfg_resp.status_code == 201
    feishu_config_id = feishu_cfg_resp.json()["id"]

    trigger_resp = await client.post(f"/api/v1/feishu-sync/configs/{feishu_config_id}/trigger")
    assert trigger_resp.status_code == 200
    assert trigger_resp.json()["ok"] is True
    assert trigger_resp.json()["records_created"] == 1
    return feishu_config_id


async def _create_and_complete_mission(client: AsyncClient, ctx: _TestContext) -> str:
    async with ctx.session_maker() as session:
        task = (
            await session.exec(
                select(Task).where(Task.external_id == "rec-e2e-1"),
            )
        ).first()
        assert task is not None
        task_id = task.id

    mission_resp = await client.post(
        "/api/v1/missions",
        json={
            "task_id": str(task_id),
            "board_id": str(ctx.board_id),
            "goal": "Handle synced task",
            "approval_policy": "auto",
        },
    )
    assert mission_resp.status_code == 201
    mission_id = UUID(mission_resp.json()["id"])

    dispatch_resp = await client.post(
        f"/api/v1/missions/{mission_id}/dispatch",
        json={"force": False},
    )
    assert dispatch_resp.status_code == 200
    async with ctx.session_maker() as session:
        generated_subtasks = list(
            (
                await session.exec(
                    select(MissionSubtask).where(MissionSubtask.mission_id == mission_id),
                )
            ).all()
        )
        assert len(generated_subtasks) >= 1

    start_resp = await client.post(f"/api/v1/missions/{mission_id}/start")
    assert start_resp.status_code == 200

    complete_resp = await client.post(
        f"/api/v1/missions/{mission_id}/complete",
        json={
            "result_summary": "Mission completed from e2e test",
            "result_risk": "low",
            "result_next_action": "close ticket",
        },
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"
    return str(mission_id)


async def _run_feishu_conflict_resolution_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    transport = ASGITransport(app=ctx.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        feishu_config_id = await _create_and_trigger_feishu_sync(client, ctx)
        async with ctx.session_maker() as session:
            task = (await session.exec(select(Task).where(Task.external_id == "rec-e2e-1"))).first()
            assert task is not None
            task.title = "Locally edited title"
            session.add(task)
            mapping = (
                await session.exec(
                    select(FeishuTaskMapping).where(FeishuTaskMapping.task_id == task.id),
                )
            ).first()
            assert mapping is not None
            event = ActivityEvent(
                event_type="feishu_sync_conflict",
                message="Conflict detected",
                task_id=task.id,
                board_id=ctx.board_id,
            )
            session.add(event)
            await session.commit()

        mappings_resp = await client.get(f"/api/v1/feishu-sync/configs/{feishu_config_id}/mappings")
        assert mappings_resp.status_code == 200
        payload = mappings_resp.json()
        assert payload[0]["has_conflict"] is True
        assert payload[0]["task_title"] == "Locally edited title"

        resolve_resp = await client.post(
            f"/api/v1/feishu-sync/configs/{feishu_config_id}/mappings/{payload[0]['id']}/resolve",
            json={"resolution": "accept_feishu"},
        )
        assert resolve_resp.status_code == 200
        assert resolve_resp.json()["has_conflict"] is False

        async with ctx.session_maker() as session:
            task = (await session.exec(select(Task).where(Task.external_id == "rec-e2e-1"))).first()
            assert task is not None
            assert task.title == "E2E synced task"


async def _run_feishu_sync_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            feishu_config_id = await _create_and_trigger_feishu_sync(client, ctx)

            history_resp = await client.get(
                f"/api/v1/feishu-sync/configs/{feishu_config_id}/history"
            )
            assert history_resp.status_code == 200
            history_directions = {item["direction"] for item in history_resp.json()}
            assert "pull" in history_directions
    finally:
        await ctx.engine.dispose()


async def _run_mission_timeline_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)
            mission_id = await _create_and_complete_mission(client, ctx)

            timeline_resp = await client.get(f"/api/v1/missions/{mission_id}/timeline")
            assert timeline_resp.status_code == 200
            timeline = timeline_resp.json()
            timeline_event_types = {item["event_type"] for item in timeline}
            assert "mission_created" in timeline_event_types
            assert "mission_completed" in timeline_event_types
            created_entry = next(
                item for item in timeline if item["event_type"] == "mission_created"
            )
            completed_entry = next(
                item for item in timeline if item["event_type"] == "mission_completed"
            )
            assert created_entry["stage"] == "created"
            assert created_entry["stage_label"] == "已创建"
            assert created_entry["tone"] == "info"
            assert completed_entry["stage"] == "result"
            assert completed_entry["status_hint"] == "completed"
    finally:
        await ctx.engine.dispose()


async def _run_notification_confirm_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)
            await _create_and_complete_mission(client, ctx)

            logs_resp = await client.get("/api/v1/notifications/logs")
            assert logs_resp.status_code == 200
            logs = logs_resp.json()
            logged_events = {item["event_type"] for item in logs}
            assert "mission_created" in logged_events
            assert "mission_completed" in logged_events

            first_log_id = logs[0]["id"]
            confirm_resp = await client.post(
                f"/api/v1/notifications/confirm/{first_log_id}",
                json={"action": "rejected", "comment": "manual reject"},
            )
            assert confirm_resp.status_code == 200
            assert confirm_resp.json()["status"] == "failed"

        async with ctx.session_maker() as session:
            log_rows = list((await session.exec(select(NotificationLog))).all())
            assert len(log_rows) >= 2
    finally:
        await ctx.engine.dispose()


async def _run_pending_approval_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            cfg_resp = await client.post(
                "/api/v1/notifications/configs",
                json={
                    "organization_id": str(ctx.org_id),
                    "board_id": str(ctx.board_id),
                    "channel_type": "feishu_bot",
                    "channel_config": {},
                    "notify_on_events": ["approval_requested"],
                    "enabled": True,
                },
            )
            assert cfg_resp.status_code == 201

            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Require review for failed execution",
                    "approval_policy": "post_review",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            subtasks = subtasks_resp.json()
            assert len(subtasks) >= 1
            subtask_id = subtasks[0]["id"]

            failed_subtask_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "failed",
                    "error_message": "intentional test failure",
                    "result_risk": "high",
                },
            )
            assert failed_subtask_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={},
            )
            assert complete_resp.status_code == 200
            completed_payload = complete_resp.json()
            assert completed_payload["status"] == "pending_approval"
            assert completed_payload["approval_id"] is not None

            logs_resp = await client.get("/api/v1/notifications/logs")
            assert logs_resp.status_code == 200
            logs = logs_resp.json()
            assert "approval_requested" in {item["event_type"] for item in logs}

        async with ctx.session_maker() as session:
            approvals = list((await session.exec(select(Approval))).all())
            assert len(approvals) >= 1
            assert approvals[0].status == "pending"
    finally:
        await ctx.engine.dispose()


async def _run_approval_resolution_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            cfg_resp = await client.post(
                "/api/v1/notifications/configs",
                json={
                    "organization_id": str(ctx.org_id),
                    "board_id": str(ctx.board_id),
                    "channel_type": "feishu_bot",
                    "channel_config": {},
                    "notify_on_events": ["approval_granted"],
                    "enabled": True,
                },
            )
            assert cfg_resp.status_code == 201

            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Approval resolution should complete mission",
                    "approval_policy": "post_review",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            first_subtask_id = subtasks_resp.json()[0]["id"]
            failed_subtask_resp = await client.patch(
                f"/api/v1/missions/subtasks/{first_subtask_id}",
                json={
                    "status": "failed",
                    "error_message": "approval path test",
                    "result_risk": "high",
                },
            )
            assert failed_subtask_resp.status_code == 200

            pending_resp = await client.post(f"/api/v1/missions/{mission_id}/complete", json={})
            assert pending_resp.status_code == 200
            pending_payload = pending_resp.json()
            assert pending_payload["status"] == "pending_approval"
            approval_id = pending_payload["approval_id"]
            assert approval_id is not None

            approve_resp = await client.patch(
                f"/api/v1/boards/{ctx.board_id}/approvals/{approval_id}",
                json={"status": "approved"},
            )
            assert approve_resp.status_code == 200
            assert approve_resp.json()["status"] == "approved"

            mission_after = await client.get(f"/api/v1/missions/{mission_id}")
            assert mission_after.status_code == 200
            assert mission_after.json()["status"] == "completed"

        async with ctx.session_maker() as session:
            task = (
                await session.exec(
                    select(Task).where(Task.external_id == "rec-e2e-1"),
                )
            ).first()
            assert task is not None
            assert task.status == "done"
    finally:
        await ctx.engine.dispose()


async def _run_approval_rejection_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Approval rejection should fail mission",
                    "approval_policy": "post_review",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            first_subtask_id = subtasks_resp.json()[0]["id"]
            failed_subtask_resp = await client.patch(
                f"/api/v1/missions/subtasks/{first_subtask_id}",
                json={
                    "status": "failed",
                    "error_message": "reject path test",
                    "result_risk": "high",
                },
            )
            assert failed_subtask_resp.status_code == 200

            pending_resp = await client.post(f"/api/v1/missions/{mission_id}/complete", json={})
            assert pending_resp.status_code == 200
            pending_payload = pending_resp.json()
            assert pending_payload["status"] == "pending_approval"
            approval_id = pending_payload["approval_id"]
            assert approval_id is not None

            reject_resp = await client.patch(
                f"/api/v1/boards/{ctx.board_id}/approvals/{approval_id}",
                json={"status": "rejected"},
            )
            assert reject_resp.status_code == 200
            assert reject_resp.json()["status"] == "rejected"

            mission_after = await client.get(f"/api/v1/missions/{mission_id}")
            assert mission_after.status_code == 200
            mission_after_payload = mission_after.json()
            assert mission_after_payload["status"] == "failed"
            assert mission_after_payload["error_message"] is not None
            assert mission_after_payload["result_next_action"] is not None

        async with ctx.session_maker() as session:
            task = (
                await session.exec(
                    select(Task).where(Task.external_id == "rec-e2e-1"),
                )
            ).first()
            assert task is not None
            assert task.status == "inbox"
            assert task.result_next_action is not None
            assert "retry" in task.result_next_action.lower()
    finally:
        await ctx.engine.dispose()


async def _run_subagent_dispatch_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    sent_messages: list[dict[str, object]] = []

    async def _fake_optional_gateway_config_for_board(self: object, board: Board) -> object:
        del self, board
        return object()

    async def _fake_send_agent_message(
        self: object,
        *,
        session_key: str,
        config: object,
        agent_name: str,
        message: str,
        deliver: bool = False,
    ) -> None:
        del self, config
        sent_messages.append(
            {
                "session_key": session_key,
                "agent_name": agent_name,
                "message": message,
                "deliver": deliver,
            }
        )

    monkeypatch.setattr(
        "app.services.openclaw.gateway_dispatch.GatewayDispatchService.optional_gateway_config_for_board",
        _fake_optional_gateway_config_for_board,
    )
    monkeypatch.setattr(
        "app.services.openclaw.gateway_dispatch.GatewayDispatchService.send_agent_message",
        _fake_send_agent_message,
    )
    monkeypatch.setattr("app.core.config.settings.auth_mode", "local")
    monkeypatch.setattr(
        "app.core.config.settings.local_auth_token",
        "local-dev-token-openclaw-mission-control-2026-bootstrap-abcdef",
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Dispatch decomposed subtasks into dedicated subagent sessions",
                    "approval_policy": "auto",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            subtasks = subtasks_resp.json()
            assert len(subtasks) >= 2
            assigned_ids = [item["assigned_subagent_id"] for item in subtasks]
            assert all(assigned_ids)
            assert len(set(assigned_ids)) == len(assigned_ids)
            assert len(sent_messages) == len(subtasks)
            assert all(item["deliver"] is True for item in sent_messages)
            assert all(
                "/api/v1/missions/subtasks/" in str(item["message"]) for item in sent_messages
            )
            assert all("Authorization: Bearer " in str(item["message"]) for item in sent_messages)
    finally:
        await ctx.engine.dispose()


async def _run_preapprove_dispatch_gate_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            cfg_resp = await client.post(
                "/api/v1/notifications/configs",
                json={
                    "organization_id": str(ctx.org_id),
                    "board_id": str(ctx.board_id),
                    "channel_type": "feishu_bot",
                    "channel_config": {},
                    "notify_on_events": ["approval_requested"],
                    "enabled": True,
                },
            )
            assert cfg_resp.status_code == 201

            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Urgent dispatch should stop for pre-approval",
                    "approval_policy": "pre_approve",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200
            dispatch_payload = dispatch_resp.json()
            assert dispatch_payload["status"] == "pending_approval"

            mission_after = await client.get(f"/api/v1/missions/{mission_id}")
            assert mission_after.status_code == 200
            assert mission_after.json()["status"] == "pending_approval"

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            assert subtasks_resp.json() == []

            logs_resp = await client.get("/api/v1/notifications/logs")
            assert logs_resp.status_code == 200
            logs = logs_resp.json()
            assert "approval_requested" in {item["event_type"] for item in logs}
    finally:
        await ctx.engine.dispose()


async def _run_preapprove_resolution_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Pre-approval should resume dispatch after approval",
                    "approval_policy": "pre_approve",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200
            assert dispatch_resp.json()["status"] == "pending_approval"

            approve_resp = await client.post(f"/api/v1/missions/{mission_id}/approve")
            assert approve_resp.status_code == 200
            approved_payload = approve_resp.json()
            assert approved_payload["status"] == "dispatched"
            assert approved_payload["approval_policy"] == "auto"

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            assert len(subtasks_resp.json()) >= 1
    finally:
        await ctx.engine.dispose()


async def _run_auto_aggregation_after_last_subtask_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Auto aggregate after the final subtask reports back",
                    "approval_policy": "auto",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            start_resp = await client.post(f"/api/v1/missions/{mission_id}/start")
            assert start_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            subtasks = subtasks_resp.json()
            assert len(subtasks) >= 2

            for index, subtask in enumerate(subtasks):
                patch_resp = await client.patch(
                    f"/api/v1/missions/subtasks/{subtask['id']}",
                    json={
                        "status": "completed",
                        "result_summary": f"subtask-{index + 1}-done",
                        "result_risk": "low",
                    },
                )
                assert patch_resp.status_code == 200

            mission_after = await client.get(f"/api/v1/missions/{mission_id}")
            assert mission_after.status_code == 200
            payload = mission_after.json()
            assert payload["status"] == "completed"
            assert payload["result_evidence"] is not None
            assert payload["result_evidence"]["stats"]["completed"] == len(subtasks)

            timeline_resp = await client.get(f"/api/v1/missions/{mission_id}/timeline")
            assert timeline_resp.status_code == 200
            timeline = timeline_resp.json()
            event_types = {item["event_type"] for item in timeline}
            assert "subtask_completed" in event_types
            assert "mission_completed" in event_types
            subtask_entry = next(
                item for item in timeline if item["event_type"] == "subtask_completed"
            )
            assert subtask_entry["stage"] == "subtask"
            assert subtask_entry["tone"] == "success"
    finally:
        await ctx.engine.dispose()


async def _run_subtask_redispatch_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = await _bootstrap(monkeypatch)
    sent_messages: list[str] = []

    async def _fake_optional_gateway_config_for_board(self: object, board: Board) -> object:
        del self, board
        return object()

    async def _fake_send_agent_message(
        self: object,
        *,
        session_key: str,
        config: object,
        agent_name: str,
        message: str,
        deliver: bool = False,
    ) -> None:
        del self, config, agent_name, deliver
        sent_messages.append(session_key)

    monkeypatch.setattr(
        "app.services.openclaw.gateway_dispatch.GatewayDispatchService.optional_gateway_config_for_board",
        _fake_optional_gateway_config_for_board,
    )
    monkeypatch.setattr(
        "app.services.openclaw.gateway_dispatch.GatewayDispatchService.send_agent_message",
        _fake_send_agent_message,
    )

    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-e2e-1"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Redispatch a failed subtask",
                    "approval_policy": "auto",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            subtasks = subtasks_resp.json()
            first_subtask = subtasks[0]

            fail_resp = await client.patch(
                f"/api/v1/missions/subtasks/{first_subtask['id']}",
                json={
                    "status": "failed",
                    "error_message": "transient error",
                    "result_risk": "high",
                },
            )
            assert fail_resp.status_code == 200

            redispatch_resp = await client.post(
                f"/api/v1/missions/subtasks/{first_subtask['id']}/redispatch"
            )
            assert redispatch_resp.status_code == 200
            redispatched = redispatch_resp.json()
            assert redispatched["status"] == "pending"
            assert redispatched["error_message"] is None
            assert redispatched["assigned_subagent_id"] is not None

            mission_after = await client.get(f"/api/v1/missions/{mission_id}")
            assert mission_after.status_code == 200
            assert mission_after.json()["status"] == "running"

            assert sent_messages.count(redispatched["assigned_subagent_id"]) >= 2
    finally:
        await ctx.engine.dispose()


def test_feishu_sync_creates_task_and_history(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_feishu_sync_flow(monkeypatch))


def test_mission_lifecycle_records_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_mission_timeline_flow(monkeypatch))


def test_notification_logs_and_confirm(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_notification_confirm_flow(monkeypatch))


def test_failed_subtask_triggers_pending_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_pending_approval_flow(monkeypatch))


def test_approved_pending_mission_becomes_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_approval_resolution_flow(monkeypatch))


def test_rejected_pending_mission_becomes_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_approval_rejection_flow(monkeypatch))


def test_subagent_dispatch_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_subagent_dispatch_flow(monkeypatch))


def test_preapprove_dispatch_gate_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_preapprove_dispatch_gate_flow(monkeypatch))


def test_preapprove_resolution_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_preapprove_resolution_flow(monkeypatch))


def test_auto_aggregation_after_last_subtask(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_auto_aggregation_after_last_subtask_flow(monkeypatch))


def test_subtask_redispatch_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_subtask_redispatch_flow(monkeypatch))


def test_feishu_conflict_resolution_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_feishu_conflict_resolution_flow(monkeypatch))
