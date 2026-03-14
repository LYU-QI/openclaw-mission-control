"""Registry for context loaders keyed by URI scheme."""

from __future__ import annotations

from typing import Protocol


class BaseContextLoader(Protocol):
    """Protocol for context source loaders."""

    async def load(self, ref: str) -> list[dict[str, str]]:
        """Load context payload from a source reference."""
        ...


class ContextRegistry:
    """Mutable registry for context loaders."""

    def __init__(self) -> None:
        self._loaders: dict[str, BaseContextLoader] = {}

    def register(self, scheme: str, loader: BaseContextLoader) -> None:
        self._loaders[scheme] = loader

    def get(self, scheme: str) -> BaseContextLoader | None:
        return self._loaders.get(scheme)
