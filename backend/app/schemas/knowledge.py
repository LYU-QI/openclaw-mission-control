from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeItemBase(BaseModel):
    board_id: UUID | None = None
    item_type: str
    title: str
    content: str
    summary: str | None = None
    source_url: str | None = None
    status: str = "suggested"


class KnowledgeItemCreate(KnowledgeItemBase):
    pass


class KnowledgeItemUpdate(BaseModel):
    board_id: UUID | None = None
    item_type: str | None = None
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    source_url: str | None = None
    status: str | None = None


class KnowledgeItemRead(KnowledgeItemBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
