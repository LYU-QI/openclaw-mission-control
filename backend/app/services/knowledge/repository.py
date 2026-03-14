"""Repository for managing knowledge assets."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import select

from app.core.time import utcnow
from app.models.knowledge import KnowledgeItem

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession


class KnowledgeRepository:
    """Handles data access and state transitions for knowledge items."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: UUID) -> KnowledgeItem | None:
        """Get a knowledge item by ID."""
        return await KnowledgeItem.objects.by_id(item_id).first(self.session)

    async def create(
        self,
        item_type: str,
        title: str,
        content: str,
        summary: str | None = None,
        source_url: str | None = None,
        board_id: UUID | None = None,
        status: str = "suggested",
    ) -> KnowledgeItem:
        """Create and persist a new knowledge item."""
        item = KnowledgeItem(
            item_type=item_type,
            title=title,
            content=content,
            summary=summary,
            source_url=source_url,
            board_id=board_id,
            status=status,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def update_status(self, item_id: UUID, new_status: str) -> KnowledgeItem:
        """Change the status (e.g. from 'suggested' to 'approved')."""
        item = await self.get_by_id(item_id)
        if not item:
            raise ValueError(f"KnowledgeItem {item_id} not found.")

        item.status = new_status
        item.updated_at = utcnow()
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(self, item_id: UUID, **kwargs: object) -> KnowledgeItem:
        """Update arbitrary fields of a knowledge item."""
        item = await self.get_by_id(item_id)
        if not item:
            raise ValueError(f"KnowledgeItem {item_id} not found.")

        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)

        item.updated_at = utcnow()
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete(self, item_id: UUID) -> None:
        """Delete a knowledge item."""
        item = await self.get_by_id(item_id)
        if item:
            await self.session.delete(item)
            await self.session.flush()
