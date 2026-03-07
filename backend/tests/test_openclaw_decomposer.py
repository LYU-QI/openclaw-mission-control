# ruff: noqa: INP001
"""Tests for task decomposition and validation."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.models.missions import Mission
from app.services.openclaw.context.loader import ContextChunk
from app.services.openclaw.decomposer.decomposer import TaskDecomposer
from app.services.openclaw.decomposer.validator import validate_subtasks


def _mission() -> Mission:
    return Mission(
        task_id=uuid4(),
        board_id=uuid4(),
        goal="Prepare launch readiness report",
        constraints={"deadline_hours": 24},
        context_refs=["doc://launch-plan"],
    )


def test_validate_subtasks_normalizes_items() -> None:
    raw = [
        {"label": "  Collect data  ", "tool_scope": "git"},
        {"label": "", "description": "invalid"},
        {"label": "Analyze", "tool_scope": ["analysis", "analysis", ""]},
    ]
    valid = validate_subtasks(raw)
    assert len(valid) == 2
    assert valid[0]["label"] == "Collect data"
    assert valid[0]["tool_scope"] == ["git"]
    assert valid[1]["tool_scope"] == ["analysis"]


def test_decompose_uses_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request(self: TaskDecomposer, prompt: str) -> str:
        del self, prompt
        return (
            '{"subtasks":[{"label":"Inspect","description":"Inspect context",'
            '"tool_scope":["context_loader"],"expected_output":"facts"}]}'
        )

    monkeypatch.setattr("app.core.config.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.core.config.settings.llm_base_url", "https://example.local/v1")
    monkeypatch.setattr(TaskDecomposer, "_request_llm", _fake_request)

    subtasks = asyncio.run(
        TaskDecomposer().decompose(
            mission=_mission(),
            context=[ContextChunk(source="doc://launch-plan", content="plan text")],
        )
    )

    assert len(subtasks) == 1
    assert subtasks[0].label == "Inspect"
    assert subtasks[0].tool_scope == ["context_loader"]


def test_decompose_falls_back_when_llm_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_request(self: TaskDecomposer, prompt: str) -> str:
        del self, prompt
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("app.core.config.settings.llm_api_key", "test-key")
    monkeypatch.setattr("app.core.config.settings.llm_base_url", "https://example.local/v1")
    monkeypatch.setattr(TaskDecomposer, "_request_llm", _fake_request)

    subtasks = asyncio.run(
        TaskDecomposer().decompose(
            mission=_mission(),
            context=[],
        )
    )

    assert len(subtasks) >= 2
    assert subtasks[0].label == "Gather Facts"


def test_build_provider_request_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.llm_provider", "openai")
    monkeypatch.setattr("app.core.config.settings.llm_api_key", "k1")
    monkeypatch.setattr("app.core.config.settings.llm_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr("app.core.config.settings.llm_model", "gpt-4o-mini")
    url, headers, payload = TaskDecomposer()._build_provider_request("hello")
    assert url.endswith("/chat/completions")
    assert headers["Authorization"] == "Bearer k1"
    assert payload["model"] == "gpt-4o-mini"


def test_build_provider_request_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.llm_provider", "azure")
    monkeypatch.setattr("app.core.config.settings.llm_api_key", "azure-key")
    monkeypatch.setattr("app.core.config.settings.llm_base_url", "https://my-azure.openai.azure.com")
    monkeypatch.setattr("app.core.config.settings.llm_model", "my-deployment")
    monkeypatch.setattr("app.core.config.settings.llm_api_version", "2024-10-21")
    url, headers, payload = TaskDecomposer()._build_provider_request("hello")
    assert "/openai/deployments/my-deployment/chat/completions" in url
    assert "api-version=2024-10-21" in url
    assert headers["api-key"] == "azure-key"
    assert payload["model"] == "my-deployment"


def test_llm_enabled_allows_local_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.llm_provider", "local")
    monkeypatch.setattr("app.core.config.settings.llm_api_key", "")
    monkeypatch.setattr("app.core.config.settings.llm_base_url", "http://localhost:11434/v1")
    assert TaskDecomposer()._llm_enabled() is True
