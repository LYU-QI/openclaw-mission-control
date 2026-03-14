import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi_pagination.ext.sqlmodel import paginate
from fastapi_pagination.limit_offset import LimitOffsetPage
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_session
from app.models.knowledge import KnowledgeItem
from app.schemas.knowledge import KnowledgeItemCreate, KnowledgeItemRead, KnowledgeItemUpdate
from app.schemas.pagination import DefaultLimitOffsetPage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=DefaultLimitOffsetPage[KnowledgeItemRead])
async def list_knowledge_items(
    session: AsyncSession = Depends(get_session),
    board_id: UUID | None = None,
    item_type: str | None = None,
    item_status: str | None = Query(None, alias="status"),
) -> LimitOffsetPage[KnowledgeItemRead]:
    """List knowledge items."""
    query = select(KnowledgeItem)
    if board_id:
        query = query.where(KnowledgeItem.board_id == board_id)
    if item_type:
        query = query.where(KnowledgeItem.item_type == item_type)
    if item_status:
        query = query.where(KnowledgeItem.status == item_status)

    query = query.order_by(KnowledgeItem.created_at.desc())  # type: ignore

    return await paginate(session, query)


@router.post("", response_model=KnowledgeItemRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_item(
    item_in: KnowledgeItemCreate,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeItem:
    """Create a new knowledge item."""
    item = KnowledgeItem.model_validate(item_in)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/{item_id}", response_model=KnowledgeItemRead)
async def get_knowledge_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeItem:
    """Get a knowledge item by ID."""
    item = await KnowledgeItem.objects.by_id(item_id).first(session)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return item


@router.patch("/{item_id}", response_model=KnowledgeItemRead)
async def update_knowledge_item(
    item_id: UUID,
    item_in: KnowledgeItemUpdate,
    session: AsyncSession = Depends(get_session),
) -> KnowledgeItem:
    """Update a knowledge item."""
    item = await KnowledgeItem.objects.by_id(item_id).first(session)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/{item_id}")
async def delete_knowledge_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    """Delete a knowledge item."""
    item = await KnowledgeItem.objects.by_id(item_id).first(session)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    await session.delete(item)
    await session.commit()
    return {"ok": True}
