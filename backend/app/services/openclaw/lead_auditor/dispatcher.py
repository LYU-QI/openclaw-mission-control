"""Lead Agent audit dispatcher for intelligent mission review."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.auth_mode import AuthMode
from app.core.config import settings
from app.models.agents import Agent
from app.models.boards import Board
from app.models.missions import Mission
from app.services.openclaw.aggregator.aggregator import AggregatedResult
from app.services.openclaw.db_service import OpenClawDBService
from app.services.openclaw.gateway_dispatch import GatewayDispatchService


def _templates_root() -> Path:
    return Path(__file__).resolve().parents[4] / "templates"


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_templates_root()),
        autoescape=select_autoescape(default=False),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )


def _callback_auth() -> tuple[str | None, str | None]:
    if settings.auth_mode == AuthMode.LOCAL and settings.local_auth_token.strip():
        return "Authorization", f"Bearer {settings.local_auth_token}"
    return None, None


def _build_audit_message(
    *,
    mission: Mission,
    task_title: str,
    aggregated: AggregatedResult,
    callback_url: str,
    auth_token: str | None,
) -> str:
    callback_auth_header, callback_auth_value = _callback_auth()

    # Extract subtask results from evidence
    subtask_results = []
    evidence = aggregated.evidence or {}
    if "subtask_results" in evidence:
        subtask_results = evidence["subtask_results"] or []

    return (
        _template_env()
        .get_template("LEAD_REVIEW.md.j2")
        .render(
            mission_id=str(mission.id),
            task_id=str(mission.task_id),
            task_title=task_title,
            mission_goal=mission.goal,
            result_summary=aggregated.summary,
            result_risk=aggregated.risk,
            result_next_action=aggregated.next_action,
            subtask_results=subtask_results,
            anomalies=aggregated.anomalies,
            callback_url=callback_url,
            auth_token=auth_token or "",
        )
        .strip()
    )


class LeadAuditDispatcher(OpenClawDBService):
    """Dispatch audit requests to Lead Agent via Gateway."""

    async def dispatch_audit(
        self,
        *,
        mission: Mission,
        task_title: str,
        board: Board,
        lead: Agent,
        aggregated: AggregatedResult,
        callback_url: str,
    ) -> bool:
        """Send audit request to Lead Agent.

        Returns:
            True if audit was dispatched successfully, False otherwise
        """
        if not lead.openclaw_session_id:
            return False

        dispatch = GatewayDispatchService(self.session)
        config = await dispatch.optional_gateway_config_for_board(board)
        if config is None:
            return False

        # Get auth token if available
        auth_token = None
        if settings.auth_mode == AuthMode.LOCAL:
            auth_token = settings.local_auth_token

        message = _build_audit_message(
            mission=mission,
            task_title=task_title,
            aggregated=aggregated,
            callback_url=callback_url,
            auth_token=auth_token,
        )

        try:
            await dispatch.send_agent_message(
                session_key=lead.openclaw_session_id,
                config=config,
                agent_name=f"Lead - {board.name}",
                message=message,
                deliver=True,
            )
            return True
        except Exception:
            return False
