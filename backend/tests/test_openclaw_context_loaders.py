# ruff: noqa: INP001
"""Tests for OpenClaw context loaders."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from app.services.openclaw.context.feishu_doc_loader import FeishuDocLoader
from app.services.openclaw.context.feishu_group_loader import FeishuGroupLoader
from app.services.openclaw.context.git_loader import GitLoader
from app.services.openclaw.context.loader import ContextLoader
from app.services.openclaw.context.log_loader import LogLoader


def test_git_loader_status(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        return subprocess.CompletedProcess(args=["git"], returncode=0, stdout="M backend/app/main.py", stderr="")

    monkeypatch.setattr("app.services.openclaw.context.git_loader.subprocess.run", _fake_run)
    chunks = asyncio.run(GitLoader().load("git://status"))
    assert len(chunks) == 1
    assert "backend/app/main.py" in chunks[0]["content"]


def test_doc_loader_reads_local_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.openclaw.context.feishu_doc_loader._repo_root", lambda: tmp_path)
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("line-1\nline-2", encoding="utf-8")
    loader = FeishuDocLoader()
    chunks = asyncio.run(loader.load("doc://design?path=doc.md"))
    assert len(chunks) == 1
    assert "line-1" in chunks[0]["content"]
    assert "line-2" in chunks[0]["content"]


def test_doc_loader_reads_remote_feishu_doc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.feishu_app_id", "cli-test")
    monkeypatch.setattr("app.core.config.settings.feishu_app_secret", "secret-test")

    def _fake_get_doc_raw_content(self: object, document_id: str) -> dict[str, object]:
        assert document_id == "doxcnRemoteDocToken"
        return {"code": 0, "data": {"content": "remote line 1\nremote line 2"}}

    monkeypatch.setattr(
        "app.services.feishu.client.FeishuClient.get_doc_raw_content",
        _fake_get_doc_raw_content,
    )

    loader = FeishuDocLoader()
    chunks = asyncio.run(loader.load("doc://doxcnRemoteDocToken"))
    assert len(chunks) == 1
    assert chunks[0]["source"] == "feishu-doc:doxcnRemoteDocToken"
    assert "remote line 1" in chunks[0]["content"]


def test_group_loader_reads_remote_feishu_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.feishu_app_id", "cli-test")
    monkeypatch.setattr("app.core.config.settings.feishu_app_secret", "secret-test")

    def _fake_list_chat_messages(
        self: object,
        chat_id: str,
        *,
        page_size: int = 20,
        sort_type: str = "ByCreateTimeAsc",
    ) -> dict[str, object]:
        assert chat_id == "oc_test_group"
        assert page_size == 20
        assert sort_type == "ByCreateTimeAsc"
        return {
            "code": 0,
            "data": {
                "items": [
                    {
                        "sender": {"sender_id": {"open_id": "ou_user_1"}},
                        "body": {"content": "first line"},
                    },
                    {
                        "sender": {"sender_id": {"open_id": "ou_user_2"}},
                        "body": {"content": "second line"},
                    },
                ]
            },
        }

    monkeypatch.setattr(
        "app.services.feishu.client.FeishuClient.list_chat_messages",
        _fake_list_chat_messages,
    )

    loader = FeishuGroupLoader()
    chunks = asyncio.run(loader.load("feishu://oc_test_group"))
    assert len(chunks) == 1
    assert chunks[0]["source"] == "feishu-group:oc_test_group"
    assert "ou_user_1: first line" in chunks[0]["content"]
    assert "ou_user_2: second line" in chunks[0]["content"]


def test_log_loader_tails_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.services.openclaw.context.log_loader._repo_root", lambda: tmp_path)
    log_file = tmp_path / "app.log"
    log_file.write_text("a\nb\nc\nd", encoding="utf-8")
    loader = LogLoader()
    chunks = asyncio.run(loader.load("log://file?path=app.log&tail=2"))
    assert len(chunks) == 1
    assert chunks[0]["content"] == "c\nd"


def test_context_loader_truncates_large_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class _HugeLoader:
        async def load(self, ref: str) -> list[dict[str, str]]:
            del ref
            return [{"source": "x://y", "content": "A" * 50000}]

    loader = ContextLoader()
    loader.registry.register("x", _HugeLoader())
    chunks = asyncio.run(loader.load(["x://y"]))
    assert len(chunks) == 1
    assert chunks[0].content.endswith("...[truncated]...")


def test_context_loader_times_out_slow_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    class _SlowLoader:
        async def load(self, ref: str) -> list[dict[str, str]]:
            del ref
            await asyncio.sleep(2)
            return [{"source": "slow://x", "content": "never"}]

    monkeypatch.setattr("app.core.config.settings.context_loader_timeout_seconds", 1)
    loader = ContextLoader()
    loader.registry.register("slow", _SlowLoader())
    chunks = asyncio.run(loader.load(["slow://x"]))
    assert len(chunks) == 1
    assert "Context load failed" in chunks[0].content
