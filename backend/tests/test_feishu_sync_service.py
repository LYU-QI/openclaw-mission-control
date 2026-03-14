from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.core.time import utcnow
from app.models.feishu_sync import FeishuSyncConfig, FeishuTaskMapping
from app.models.tasks import Task
from app.services.feishu.conflict_resolver import ConflictResolver
from app.services.feishu.sync_service import SyncService


def _service() -> SyncService:
    config = FeishuSyncConfig(
        id=uuid4(),
        organization_id=uuid4(),
        board_id=uuid4(),
        app_id="cli_x",
        app_secret_encrypted="secret",
        bitable_app_token="app_token",
        bitable_table_id="tbl_x",
        field_mapping={},
    )
    service = object.__new__(SyncService)
    service.config = config
    service.conflict_resolver = ConflictResolver()
    service.mapper = SimpleNamespace(
        to_feishu=lambda task: {"任务名称": task.title},
        to_mc=lambda fields: {"title": fields.get("任务名称")},
    )
    service.client = SimpleNamespace(
        update_bitable_record=lambda *args, **kwargs: {"code": 0},
        get_bitable_record=lambda *args, **kwargs: {
            "code": 0,
            "data": {"record": {"fields": {"任务名称": "Feishu title"}}},
        },
    )
    service.session = None
    return service


def test_has_local_conflict_returns_false_for_same_hash() -> None:
    service = _service()
    now = utcnow()
    task = Task(
        id=uuid4(),
        board_id=uuid4(),
        title="Task",
        updated_at=now + timedelta(minutes=5),
    )
    mapping = FeishuTaskMapping(
        id=uuid4(),
        sync_config_id=uuid4(),
        feishu_record_id="rec_1",
        task_id=task.id,
        sync_hash="same-hash",
        last_feishu_update=now,
    )

    assert service._has_local_conflict(mapping=mapping, task=task, new_hash="same-hash") is False


def test_has_local_conflict_returns_true_when_local_is_newer() -> None:
    service = _service()
    now = utcnow()
    task = Task(
        id=uuid4(),
        board_id=uuid4(),
        title="Task",
        updated_at=now + timedelta(minutes=10),
    )
    mapping = FeishuTaskMapping(
        id=uuid4(),
        sync_config_id=uuid4(),
        feishu_record_id="rec_1",
        task_id=task.id,
        sync_hash="old-hash",
        last_feishu_update=now,
    )

    assert service._has_local_conflict(mapping=mapping, task=task, new_hash="new-hash") is True


def test_has_local_conflict_returns_false_when_feishu_is_not_older() -> None:
    service = _service()
    now = utcnow()
    task = Task(
        id=uuid4(),
        board_id=uuid4(),
        title="Task",
        updated_at=now - timedelta(minutes=1),
    )
    mapping = FeishuTaskMapping(
        id=uuid4(),
        sync_config_id=uuid4(),
        feishu_record_id="rec_1",
        task_id=task.id,
        sync_hash="old-hash",
        last_feishu_update=now,
    )

    assert service._has_local_conflict(mapping=mapping, task=task, new_hash="new-hash") is False


def test_resolve_conflict_keep_local_updates_mapping_fields() -> None:
    service = _service()
    now = utcnow()
    task = Task(id=uuid4(), board_id=uuid4(), title="Local title", updated_at=now)
    mapping = FeishuTaskMapping(
        id=uuid4(),
        sync_config_id=service.config.id,
        feishu_record_id="rec_1",
        task_id=task.id,
        sync_hash="old-hash",
        last_feishu_update=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    class _TaskObjects:
        @staticmethod
        def by_id(task_id: object) -> object:
            del task_id

            class _Query:
                @staticmethod
                async def first(session: object) -> Task:
                    del session
                    return task

            return _Query()

    async def _noop_commit() -> None:
        return None

    async def _noop_refresh(_: object) -> None:
        return None

    service.session = SimpleNamespace(
        add=lambda _: None, commit=_noop_commit, refresh=_noop_refresh
    )
    original_objects = Task.objects
    Task.objects = _TaskObjects()  # type: ignore[assignment]
    try:
        updated = __import__("asyncio").run(service.resolve_conflict_keep_local(mapping))
    finally:
        Task.objects = original_objects  # type: ignore[assignment]

    assert updated.sync_hash is not None
    assert updated.last_feishu_update is not None
    assert updated.last_mc_update == task.updated_at


def test_resolve_conflict_accept_feishu_overwrites_task_title() -> None:
    service = _service()
    now = utcnow()
    task = Task(id=uuid4(), board_id=uuid4(), title="Local title", updated_at=now)
    mapping = FeishuTaskMapping(
        id=uuid4(),
        sync_config_id=service.config.id,
        feishu_record_id="rec_1",
        task_id=task.id,
        sync_hash="old-hash",
        last_feishu_update=now - timedelta(minutes=5),
        updated_at=now - timedelta(minutes=5),
    )

    class _TaskObjects:
        @staticmethod
        def by_id(task_id: object) -> object:
            del task_id

            class _Query:
                @staticmethod
                async def first(session: object) -> Task:
                    del session
                    return task

            return _Query()

    async def _noop_commit() -> None:
        return None

    async def _noop_refresh(_: object) -> None:
        return None

    service.session = SimpleNamespace(
        add=lambda _: None, commit=_noop_commit, refresh=_noop_refresh
    )
    original_objects = Task.objects
    Task.objects = _TaskObjects()  # type: ignore[assignment]
    try:
        updated = __import__("asyncio").run(service.resolve_conflict_accept_feishu(mapping))
    finally:
        Task.objects = original_objects  # type: ignore[assignment]

    assert task.title == "Feishu title"
    assert updated.sync_hash is not None
