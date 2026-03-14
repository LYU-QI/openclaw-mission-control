from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.knowledge import KnowledgeItem
from app.schemas.knowledge import KnowledgeItemCreate, KnowledgeItemUpdate
from app.services.knowledge.repository import KnowledgeRepository


@dataclass
class _FakeExecResult:
    """Mimics the minimal SQLModel result API used in services."""

    first_value: Any = None
    all_values: list[Any] | None = None

    def first(self) -> Any:
        return self.first_value

    def all(self) -> list[Any]:
        return self.all_values or []

    def __iter__(self):
        return iter(self.all_values or [])


@dataclass
class _FakeSession:
    exec_results: list[Any] = field(default_factory=list)
    added: list[Any] = field(default_factory=list)
    committed: int = 0
    refreshed: list[Any] = field(default_factory=list)
    deleted: list[Any] = field(default_factory=list)
    flushed: int = 0

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            return _FakeExecResult()
        return self.exec_results.pop(0)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed += 1

    async def flush(self) -> None:
        self.flushed += 1

    async def refresh(self, value: Any) -> None:
        self.refreshed.append(value)

    async def delete(self, value: Any) -> None:
        self.deleted.append(value)

    async def get(self, model: type[Any], key: Any) -> Any:
        for item in self.added:
            if hasattr(item, "id") and item.id == key:
                return item
        return None


@pytest.mark.asyncio
async def test_knowledge_repository_create() -> None:
    session: Any = _FakeSession()
    repo = KnowledgeRepository(session)

    item = await repo.create(
        item_type="faq",
        title="测试知识点",
        content="这是测试内容",
        summary="摘要",
        status="suggested",
    )

    assert item.title == "测试知识点"
    assert item.item_type == "faq"
    assert item.status == "suggested"
    assert len(session.added) == 1
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_knowledge_repository_get_by_id_not_found_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session: Any = _FakeSession()
    repo = KnowledgeRepository(session)

    # 模拟 get_by_id 返回 None，验证业务逻辑抛出异常
    # 注意：Repository 目前实现中 get_by_id 找不到返回 None，update 等方法会基于此抛异常。
    # 我们测试 update_status 找不到的情况。

    async def mock_get_by_id(self, item_id):
        return None

    monkeypatch.setattr(KnowledgeRepository, "get_by_id", mock_get_by_id)

    with pytest.raises(ValueError) as exc:
        await repo.update_status(uuid4(), "approved")
    assert "not found" in str(exc.value)


@pytest.mark.asyncio
async def test_knowledge_repository_update_status(monkeypatch: pytest.MonkeyPatch) -> None:
    item_id = uuid4()
    existing = KnowledgeItem(
        id=item_id, title="旧标题", content="内容", item_type="decision", status="suggested"
    )

    async def mock_get_by_id(self, id):
        return existing

    monkeypatch.setattr(KnowledgeRepository, "get_by_id", mock_get_by_id)

    session: Any = _FakeSession()
    repo = KnowledgeRepository(session)

    updated = await repo.update_status(item_id, "approved")

    assert updated.status == "approved"
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_knowledge_repository_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    item_id = uuid4()
    existing = KnowledgeItem(id=item_id, title="D", content="C", item_type="faq")

    async def mock_get_by_id(self, id):
        return existing

    monkeypatch.setattr(KnowledgeRepository, "get_by_id", mock_get_by_id)

    session: Any = _FakeSession()
    repo = KnowledgeRepository(session)

    await repo.delete(item_id)

    assert len(session.deleted) == 1
    assert session.flushed == 1


# --- Extractor Tests ---
from app.services.knowledge.extractor import KnowledgeExtractor


@pytest.mark.asyncio
async def test_knowledge_extractor_ingest_chat_log() -> None:
    session: Any = _FakeSession()
    extractor = KnowledgeExtractor(session)

    chat_log = "User: 如何配置网关？ Agent: 在管理页面点击添加网关。"
    # 修正方法名和参数
    await extractor.ingest_from_chat_log(board_id=uuid4(), chat_transcript=chat_log)

    assert len(session.added) == 1
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_knowledge_extractor_summarize_incident() -> None:
    session: Any = _FakeSession()
    extractor = KnowledgeExtractor(session)

    report = "事件：数据库连接超时。原因：连接池满。解决：增加池大小。"
    # 修正参数
    await extractor.summarize_incident(
        board_id=uuid4(), incident_report=report, incident_id="INC-123"
    )

    assert session.flushed == 1


# --- API Tests ---
from app.api import knowledge as knowledge_api
from app.schemas.knowledge import KnowledgeItemCreate


@pytest.mark.asyncio
async def test_api_create_knowledge_item() -> None:
    session: Any = _FakeSession()
    payload = KnowledgeItemCreate(title="API测试", content="API内容", item_type="context")

    # 修正参数名为 item_in
    item = await knowledge_api.create_knowledge_item(item_in=payload, session=session)

    assert item.title == "API测试"
    assert item.item_type == "context"
    assert session.committed == 1


@pytest.mark.asyncio
async def test_api_list_knowledge_items(monkeypatch: pytest.MonkeyPatch) -> None:
    session: Any = _FakeSession()

    # 绕过 paginate 的复杂 SQLModel 依赖，通过 monkeypatch 模拟返回值
    mock_items = [KnowledgeItem(id=uuid4(), title="I1", content="C1", item_type="faq")]

    # 必须直接 mock 掉 api.knowledge 里的 paginate 引用
    async def mock_paginate(session, query):
        from types import SimpleNamespace

        return SimpleNamespace(items=mock_items, total=1, limit=50, offset=0)

    monkeypatch.setattr(knowledge_api, "paginate", mock_paginate)

    response = await knowledge_api.list_knowledge_items(session=session)

    assert len(response.items) == 1
    assert response.items[0].title == "I1"
