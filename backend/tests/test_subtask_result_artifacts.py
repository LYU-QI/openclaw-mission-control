# ruff: noqa: INP001
"""Tests for subtask result_evidence with various artifact types."""

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
class _ArtifactTestContext:
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
                        "record_id": "rec-artifact-test",
                        "fields": {
                            "title_col": "Artifact Test Task",
                            "desc_col": "Testing various artifact types",
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
                        "title_col": "Artifact Test Task",
                        "desc_col": "Testing various artifact types",
                        "priority_col": "high",
                        "status_col": "todo",
                    },
                },
            },
        }

    monkeypatch.setattr(FeishuClient, "list_bitable_records", _fake_list_bitable_records)
    monkeypatch.setattr(FeishuClient, "update_bitable_record", _fake_update_bitable_record)
    monkeypatch.setattr(FeishuClient, "get_bitable_record", _fake_get_bitable_record)


async def _bootstrap(monkeypatch: pytest.MonkeyPatch) -> _ArtifactTestContext:
    engine = await _make_engine()
    session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        org = Organization(id=uuid4(), name="Artifact Test Org")
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
            name="Artifact Test Board",
            slug="artifact-test-board",
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
    return _ArtifactTestContext(
        engine=engine,
        session_maker=session_maker,
        app=app,
        org_id=org.id,
        board_id=board.id,
    )


async def _create_notification_config(client: AsyncClient, ctx: _ArtifactTestContext) -> None:
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


async def _create_and_trigger_feishu_sync(client: AsyncClient, ctx: _ArtifactTestContext) -> str:
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


# ============================================================================
# Test Cases for Various Artifact Types
# ============================================================================


async def _run_html_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test HTML artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            # Create mission
            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate an HTML game",
                    "approval_policy": "auto",
                },
            )
            assert mission_resp.status_code == 201
            mission_id = mission_resp.json()["id"]

            # Dispatch
            dispatch_resp = await client.post(
                f"/api/v1/missions/{mission_id}/dispatch",
                json={"force": False},
            )
            assert dispatch_resp.status_code == 200

            # Start mission
            start_resp = await client.post(f"/api/v1/missions/{mission_id}/start")
            assert start_resp.status_code == 200

            # Get subtasks
            subtasks_resp = await client.get(f"/api/v1/missions/{mission_id}/subtasks")
            assert subtasks_resp.status_code == 200
            subtasks = subtasks_resp.json()
            assert len(subtasks) >= 1
            subtask_id = subtasks[0]["id"]

            # Complete subtask with HTML artifact (as dict, not JSON string)
            html_evidence = {
                "artifacts": [
                    "贪吃蛇游戏 - /artifacts/snake_game.html"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Successfully created snake game",
                    "result_evidence": html_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            # Complete mission
            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Mission completed",
                    "result_risk": "low",
                    "result_next_action": "Review in group",
                },
            )
            assert complete_resp.status_code == 200

            # Check notification logs contain artifact link
            logs_resp = await client.get("/api/v1/notifications/logs")
            assert logs_resp.status_code == 200
            logs = logs_resp.json()

            # Find mission_completed log
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            # Check extra payload contains artifact info
            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "snake_game.html" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_image_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PNG/JPG image artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                assert task is not None
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate a chart image",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with PNG artifact (as dict, not JSON string)
            png_evidence = {
                "artifacts": [
                    "销售图表 - /artifacts/sales_chart.png"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Created sales chart",
                    "result_evidence": png_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Chart created",
                    "result_risk": "low",
                    "result_next_action": "View in group",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "sales_chart.png" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_pdf_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test PDF artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate a PDF report",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with PDF artifact (as dict)
            pdf_evidence = {
                "artifacts": [
                    "Q1报告 - /artifacts/q1_report.pdf"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Generated Q1 report",
                    "result_evidence": pdf_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "PDF created",
                    "result_risk": "low",
                    "result_next_action": "Download PDF",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "q1_report.pdf" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_json_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test JSON artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Export data as JSON",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with JSON artifact (as dict)
            json_evidence = {
                "artifacts": [
                    "用户数据 - /artifacts/users.json"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Exported user data",
                    "result_evidence": json_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "JSON exported",
                    "result_risk": "low",
                    "result_next_action": "View JSON",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "users.json" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_markdown_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Markdown artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate documentation",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with MD artifact (as dict)
            md_evidence = {
                "artifacts": [
                    "API文档 - /artifacts/api_docs.md"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Generated API documentation",
                    "result_evidence": md_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Documentation created",
                    "result_risk": "low",
                    "result_next_action": "Read docs",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "api_docs.md" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_python_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test Python script artifact result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Write a Python script",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with Python artifact (as dict)
            py_evidence = {
                "artifacts": [
                    "数据处理脚本 - /artifacts/data_processor.py"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Created data processing script",
                    "result_evidence": py_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Script created",
                    "result_risk": "low",
                    "result_next_action": "Run script",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "data_processor.py" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_multiple_artifacts_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multiple artifacts in result_evidence."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate multiple output files",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with multiple artifacts (as dict)
            multi_evidence = {
                "artifacts": [
                    "游戏 - /artifacts/game.html",
                    "说明文档 - /artifacts/README.md",
                    "数据 - /artifacts/data.json",
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Created multiple files",
                    "result_evidence": multi_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "All files created",
                    "result_risk": "low",
                    "result_next_action": "View all files",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            # Should contain all artifacts
            assert "game.html" in extra["subtask_results"]
            assert "README.md" in extra["subtask_results"]
            assert "data.json" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_http_url_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test HTTP URL artifact (not local file)."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Search for information",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with HTTP URL artifact (as dict)
            url_evidence = {
                "artifacts": [
                    "搜索结果 - https://example.com/search-results"
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Found search results",
                    "result_evidence": url_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Search completed",
                    "result_risk": "low",
                    "result_next_action": "View results",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            # HTTP URL should be preserved as-is
            assert "https://example.com/search-results" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_dict_format_artifact_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test artifact as dict format (not string)."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Generate structured output",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete with dict format artifact (as dict)
            dict_evidence = {
                "artifacts": [
                    {
                        "name": "分析报告",
                        "url": "/artifacts/analysis_report.html"
                    }
                ]
            }

            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Generated analysis report",
                    "result_evidence": dict_evidence,
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "Report generated",
                    "result_risk": "low",
                    "result_next_action": "View report",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            assert "subtask_results" in extra
            assert "analysis_report.html" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


async def _run_no_artifacts_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test mission completion without artifacts (text only)."""
    ctx = await _bootstrap(monkeypatch)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=ctx.app),
            base_url="http://testserver",
        ) as client:
            await _create_notification_config(client, ctx)
            await _create_and_trigger_feishu_sync(client, ctx)

            async with ctx.session_maker() as session:
                task = (
                    await session.exec(
                        select(Task).where(Task.external_id == "rec-artifact-test"),
                    )
                ).first()
                task_id = task.id

            mission_resp = await client.post(
                "/api/v1/missions",
                json={
                    "task_id": str(task_id),
                    "board_id": str(ctx.board_id),
                    "goal": "Simple text task",
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
            subtasks = subtasks_resp.json()
            subtask_id = subtasks[0]["id"]

            # Complete without artifacts
            patch_resp = await client.patch(
                f"/api/v1/missions/subtasks/{subtask_id}",
                json={
                    "status": "completed",
                    "result_summary": "Task completed successfully",
                    "result_risk": "low",
                },
            )
            assert patch_resp.status_code == 200

            complete_resp = await client.post(
                f"/api/v1/missions/{mission_id}/complete",
                json={
                    "result_summary": "All done",
                    "result_risk": "low",
                    "result_next_action": "Close task",
                },
            )
            assert complete_resp.status_code == 200

            logs_resp = await client.get("/api/v1/notifications/logs")
            logs = logs_resp.json()
            completed_logs = [log for log in logs if log["event_type"] == "mission_completed"]
            assert len(completed_logs) >= 1

            extra = completed_logs[0].get("payload", {})
            # Should still have subtask_results but no artifact links
            assert "subtask_results" in extra
            # Should contain the result summary
            assert "Task completed successfully" in extra["subtask_results"]
    finally:
        await ctx.engine.dispose()


# ============================================================================
# Pytest Test Functions
# ============================================================================


def test_html_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_html_artifact_test(monkeypatch))


def test_png_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_image_artifact_test(monkeypatch))


def test_pdf_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_pdf_artifact_test(monkeypatch))


def test_json_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_json_artifact_test(monkeypatch))


def test_markdown_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_markdown_artifact_test(monkeypatch))


def test_python_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_python_artifact_test(monkeypatch))


def test_multiple_artifacts_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_multiple_artifacts_test(monkeypatch))


def test_http_url_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_http_url_artifact_test(monkeypatch))


def test_dict_format_artifact_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_dict_format_artifact_test(monkeypatch))


def test_no_artifacts_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    asyncio.run(_run_no_artifacts_test(monkeypatch))
