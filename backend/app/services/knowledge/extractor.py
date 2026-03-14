"""Mock extractor service for generating knowledge from external unstructured context."""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from app.services.knowledge.repository import KnowledgeRepository

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """Reliability level of the knowledge source or extraction method."""

    HIGH = "high"  # e.g., explicit user action, system-generated incident reports
    MEDIUM = "medium"  # e.g., high-quality docs parsing
    LOW = "low"  # e.g., fuzzy LLM chat summarization


def get_status_by_confidence(confidence: ConfidenceLevel) -> str:
    """Determine the knowledge item status based on extraction confidence.

    A clear boundary for auto-approval:
    Only HIGH confidence items are automatically approved.
    MEDIUM and LOW confidence items are marked as 'suggested' and await human review.
    """
    if confidence == ConfidenceLevel.HIGH:
        return "approved"
    return "suggested"


class KnowledgeExtractor:
    """Service to extract knowledge items from various sources (e.g. Feishu docs, chats).

    In a full implementation, this would call out to an LLM or specific API
    extractors to generate structured knowledge. For now, it provides mock implementations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = KnowledgeRepository(session)

    async def ingest_from_chat_log(
        self,
        board_id: UUID,
        chat_transcript: str,
        topic: str = "General Support",
        confidence: ConfidenceLevel = ConfidenceLevel.LOW,
    ) -> None:
        """Simulate extracting FAQ or Decision from a chat transcript.

        Boundary Policy:
        Multi-modal or fuzzy chat extraction inherently carries hallucination risks.
        Therefore, this defaults to LOW confidence, pushing the knowledge item into
        a 'suggested' state for human operators to review before it becomes active.
        """
        logger.info(f"Mock analyzing chat transcript for board {board_id}")

        status = get_status_by_confidence(confidence)

        # In real life: prompt LLM to extract FAQs or critical decisions from chat_transcript.
        if len(chat_transcript) > 100:
            await self.repository.create(
                item_type="faq",
                title=f"Extracted FAQ - {topic}",
                content="This is a simulated FAQ extracted from a lengthy discussion. Q: What happened? A: We discussed it.",
                summary="Auto-extracted frequently asked questions summary.",
                board_id=board_id,
                status=status,
            )
        else:
            await self.repository.create(
                item_type="decision",
                title=f"Decision extracted - {topic}",
                content="Based on a brief chat, we agreed to proceed.",
                summary="Brief architectural decision.",
                board_id=board_id,
                status=status,
            )

        logger.info(f"Finished extracting {status} knowledge for board {board_id}")

    async def summarize_incident(
        self,
        board_id: UUID,
        incident_report: str,
        incident_id: str,
        confidence: ConfidenceLevel = ConfidenceLevel.HIGH,
    ) -> None:
        """Simulate extracting structured post-mortem knowledge from an incident report.

        Boundary Policy:
        System-generated incident reports or formal post-mortems are considered
        highly reliable sources of truth. They default to HIGH confidence and
        are automatically 'approved' into the knowledge base.
        """
        logger.info(f"Mock analyzing incident report for {incident_id}")

        status = get_status_by_confidence(confidence)

        await self.repository.create(
            item_type="context",
            title=f"Post-Mortem: Incident {incident_id}",
            content=f"Incident Report Body:\n{incident_report}\n\nKey Takeaways: Ensure memory limits are increased.",
            summary=f"Context from resolved incident {incident_id}",
            board_id=board_id,
            status=status,
        )
