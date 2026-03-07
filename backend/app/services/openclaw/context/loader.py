"""Unified context loading for mission refs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.core.config import settings
from app.services.openclaw.context.context_registry import ContextRegistry
from app.services.openclaw.context.feishu_doc_loader import FeishuDocLoader
from app.services.openclaw.context.feishu_group_loader import FeishuGroupLoader
from app.services.openclaw.context.git_loader import GitLoader
from app.services.openclaw.context.log_loader import LogLoader


@dataclass(slots=True)
class ContextChunk:
    """Single context item consumed by decomposer/agents."""

    source: str
    content: str


class ContextLoader:
    """Loads context references from external systems."""

    def __init__(self) -> None:
        self.registry = ContextRegistry()
        self.registry.register("feishu", FeishuGroupLoader())
        self.registry.register("doc", FeishuDocLoader())
        self.registry.register("git", GitLoader())
        self.registry.register("log", LogLoader())
        self.registry.register("monitor", LogLoader())

    async def load(self, refs: list[str] | None) -> list[ContextChunk]:
        max_chars = max(settings.context_loader_max_tokens, 1) * 4
        timeout_seconds = max(int(settings.context_loader_timeout_seconds), 1)
        chunks: list[ContextChunk] = []
        for ref in refs or []:
            scheme = ref.split("://", 1)[0]
            loader = self.registry.get(scheme)
            if loader is None:
                continue
            try:
                raw_chunks = await asyncio.wait_for(
                    loader.load(ref),
                    timeout=timeout_seconds,
                )
            except Exception as exc:
                raw_chunks = [{"source": ref, "content": f"Context load failed: {exc}"}]
            for raw in raw_chunks:
                content = raw.get("content", "")
                if len(content) > max_chars:
                    content = f"{content[:max_chars]}\n...[truncated]..."
                chunks.append(
                    ContextChunk(
                        source=raw.get("source", ref),
                        content=content,
                    ),
                )
        return chunks
