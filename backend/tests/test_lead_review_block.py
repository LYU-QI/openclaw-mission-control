from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api import tasks as tasks_api
from app.api.deps import ActorContext
from app.core.time import utcnow
from app.models.activity_events import ActivityEvent
from app.models.agents import Agent
from app.models.boards import Board
from app.models.gateways import Gateway
from app.models.organizations import Organization
from app.models.tasks import Task
from app.schemas.tasks import TaskUpdate

async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine

async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)

@pytest.mark.asyncio
async def test_lead_agent_blocked_from_done_without_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org_id = uuid4()
            board_id = uuid4()
            gateway_id = uuid4()
            lead_id = uuid4()
            task_id = uuid4()

            session.add(Organization(id=org_id, name="org"))
            session.add(
                Gateway(
                    id=gateway_id,
                    organization_id=org_id,
                    name="gateway",
                    url="https://gateway.local",
                    workspace_root="/tmp/workspace",
                ),
            )
            session.add(
                Board(
                    id=board_id,
                    organization_id=org_id,
                    name="board",
                    slug="board",
                    gateway_id=gateway_id,
                    require_approval_for_done=False,
                ),
            )
            session.add(
                Agent(
                    id=lead_id,
                    name="Lead Agent",
                    board_id=board_id,
                    gateway_id=gateway_id,
                    status="online",
                    is_board_lead=True,
                ),
            )
            session.add(
                Task(
                    id=task_id,
                    board_id=board_id,
                    title="review task",
                    description="needs review",
                    status="review",
                    assigned_agent_id=lead_id,
                    previous_in_progress_at=utcnow(),
                ),
            )
            await session.commit()

            # Mock gateway dispatch since we don't need real gateway calls in this test
            class _FakeDispatch:
                def __init__(self, _session: AsyncSession) -> None:
                    pass
                async def optional_gateway_config_for_board(self, _board: Board) -> object:
                    return object()

            async def _fake_send_agent_task_message(*args, **kwargs) -> None:
                pass

            monkeypatch.setattr(tasks_api, "GatewayDispatchService", _FakeDispatch)
            monkeypatch.setattr(tasks_api, "_send_agent_task_message", _fake_send_agent_task_message)

            task = (await session.exec(select(Task).where(col(Task.id) == task_id))).first()
            actor = (await session.exec(select(Agent).where(col(Agent.id) == lead_id))).first()

            # 1. 尝试直接变为 done -> 预期被拦截
            with pytest.raises(HTTPException) as exc_info:
                await tasks_api.update_task(
                    payload=TaskUpdate(status="done"),
                    task=task,
                    session=session,
                    actor=ActorContext(actor_type="agent", agent=actor),
                )
            
            assert exc_info.value.status_code == 409
            assert "review comment" in exc_info.value.detail

            # 2. 模拟 Lead Agent 添加评论
            session.add(
                ActivityEvent(
                    event_type="task.comment",
                    task_id=task_id,
                    agent_id=lead_id,
                    message="LGTM, approved.",
                )
            )
            await session.commit()

            # 3. 再次尝试变为 done -> 预期成功
            updated_task = await tasks_api.update_task(
                payload=TaskUpdate(status="done"),
                task=task,
                session=session,
                actor=ActorContext(actor_type="agent", agent=actor),
            )
            assert updated_task.status == "done"

    finally:
        await engine.dispose()
