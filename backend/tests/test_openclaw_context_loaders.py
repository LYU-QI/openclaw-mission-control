# ruff: noqa: INP001
"""Tests for OpenClaw context loaders."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

import pytest

from app.services.openclaw.context.feishu_doc_loader import FeishuDocLoader
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
