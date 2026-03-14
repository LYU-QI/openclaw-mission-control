"""Knowledge management models for AI persistent context."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, Text
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel


class KnowledgeItem(QueryModel, table=True):
    """A unit of persistent knowledge (FAQ, decision, summary, context) extracted from various sources."""

    __tablename__ = "knowledge_items"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    board_id: UUID | None = Field(default=None, foreign_key="boards.id", index=True)

    # "faq" | "decision" | "summary" | "context"
    item_type: str = Field(index=True)

    title: str = Field(sa_column=Column(Text, nullable=False))
    content: str = Field(sa_column=Column(Text, nullable=False))
    summary: str | None = Field(default=None, sa_column=Column(Text))

    source_url: str | None = Field(default=None, sa_column=Column(Text))

    # "draft" | "suggested" | "approved" | "archived"
    status: str = Field(default="suggested", index=True)

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
