import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel import select

from app.models.feishu_sync import FeishuSyncConfig, FeishuTaskMapping
from app.models.tasks import Task
from app.services.feishu.field_mapper import DEFAULT_FIELD_MAPPING
from app.services.feishu.sync_service import SyncService


@dataclass
class _FakeExecResult:
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


@pytest.mark.asyncio
async def test_feishu_sync_pull_new_record(monkeypatch) -> None:
    # 1. 准备配置数据
    config = FeishuSyncConfig(
        id=uuid4(),
        organization_id=uuid4(),
        board_id=uuid4(),
        app_id="cli_123",
        app_secret_encrypted="enc_secret",
        bitable_app_token="app_token",
        bitable_table_id="table_id",
        field_mapping=DEFAULT_FIELD_MAPPING,
    )

    # 2. Mock FeishuClient
    mock_client = MagicMock()
    mock_client.list_bitable_records.return_value = {
        "code": 0,
        "data": {
            "items": [
                {
                    "record_id": "rec_001",
                    "fields": {
                        "任务名称": "来自飞书的任务",
                        "描述": "测试描述",
                        "优先级": "高",
                        "状态": "待处理",
                    },
                }
            ],
            "has_more": False,
        },
    }

    # 构建 Mock Session。
    # pull_from_feishu 内部会查 mapping (exec)
    session: Any = _FakeSession(
        exec_results=[
            _FakeExecResult(first_value=None),  # check mapping
        ]
    )

    # 用 patch 拦截 SyncService 中的 FeishuClient 构造和解密
    with (
        patch("app.services.feishu.sync_service.FeishuClient", return_value=mock_client),
        patch("app.services.feishu.sync_service.decrypt_secret", return_value="plain_secret"),
    ):

        service = SyncService(session, config)

        # 3. 执行 Pull
        stats = await service.pull_from_feishu()

        # 4. 验证统计
        assert stats["created"] == 1
        assert stats["processed"] == 1

        # 5. 验证是否生成了 Task
        task = next((it for it in session.added if isinstance(it, Task)), None)
        assert task is not None
        assert task.title == "来自飞书的任务"
        assert task.status == "inbox"


@pytest.mark.asyncio
async def test_feishu_sync_push_result(monkeypatch) -> None:
    # 1. 准备数据
    config = FeishuSyncConfig(
        id=uuid4(),
        organization_id=uuid4(),
        board_id=uuid4(),
        app_id="cli_123",
        app_secret_encrypted="enc_secret",
        bitable_app_token="app_token",
        bitable_table_id="table_id",
        field_mapping=DEFAULT_FIELD_MAPPING,
    )
    task = Task(
        id=uuid4(),
        board_id=config.board_id,
        title="MC 侧已完成任务",
        status="done",
        result_summary="AI 运行成功",
    )
    mapping = FeishuTaskMapping(
        sync_config_id=config.id, feishu_record_id="rec_002", task_id=task.id
    )

    # push_to_feishu 内部会查 mapping，然后是 Task
    session: Any = _FakeSession(
        exec_results=[
            _FakeExecResult(first_value=mapping),  # lookup mapping
            _FakeExecResult(first_value=task),  # lookup task (via Task.objects.by_id)
        ]
    )

    # 2. Mock FeishuClient
    mock_client = MagicMock()

    with (
        patch("app.services.feishu.sync_service.FeishuClient", return_value=mock_client),
        patch("app.services.feishu.sync_service.decrypt_secret", return_value="plain_secret"),
    ):

        service = SyncService(session, config)

        # 3. 执行 Push
        success = await service.push_to_feishu(task.id)
        assert success is True

        # 4. 验证 FeishuClient.update_bitable_record 被正确调用
        mock_client.update_bitable_record.assert_called_once()
        args = mock_client.update_bitable_record.call_args[0]
        assert args[3]["状态"] == "已完成"
        assert args[3]["AI执行摘要"] == "AI 运行成功"
