"""Dispatch mission subtasks to dedicated OpenClaw sessions."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from sqlmodel import select

from app.core.auth_mode import AuthMode
from app.core.config import settings
from app.core.time import utcnow
from app.models.boards import Board
from app.models.missions import Mission, MissionSubtask
from app.services.activity_log import record_activity
from app.services.openclaw.db_service import OpenClawDBService
from app.services.openclaw.gateway_dispatch import GatewayDispatchService
from app.services.openclaw.subagent_identity import MissionSubagentIdentity


def _templates_root() -> Path:
    return Path(__file__).resolve().parents[3] / "templates"


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


def _build_subtask_message(*, mission: Mission, subtask: MissionSubtask) -> str:
    callback_auth_header, callback_auth_value = _callback_auth()
    return (
        _template_env()
        .get_template("SUBTASK_EXECUTION.md.j2")
        .render(
            mission_id=str(mission.id),
            task_id=str(mission.task_id),
            board_id=str(mission.board_id),
            subtask_id=str(subtask.id),
            label=subtask.label,
            description=subtask.description or "",
            tool_scope=subtask.tool_scope or [],
            expected_output=subtask.expected_output or "",
            context_refs=mission.context_refs or [],
            callback_url=f"{settings.base_url}/api/v1/missions/subtasks/{subtask.id}",
            callback_auth_header=callback_auth_header,
            callback_auth_value=callback_auth_value,
        )
        .strip()
    )


class SubagentDispatchService(OpenClawDBService):
    """Assign and dispatch mission subtasks into dedicated gateway sessions."""

    async def dispatch_subtask(self, mission: Mission, subtask: MissionSubtask) -> MissionSubtask:
        board = await Board.objects.by_id(mission.board_id).first(self.session)
        dispatch = GatewayDispatchService(self.session)
        gateway_config = None
        if board is not None:
            gateway_config = await dispatch.optional_gateway_config_for_board(board)

        session_key = MissionSubagentIdentity.session_key(
            mission_id=mission.id,
            subtask_id=subtask.id,
        )
        subtask.assigned_subagent_id = session_key
        subtask.updated_at = utcnow()
        self.session.add(subtask)

        record_activity(
            self.session,
            event_type="subtask_dispatched",
            message=f"Subtask dispatched: {subtask.label}",
            task_id=mission.task_id,
            board_id=mission.board_id,
            agent_id=mission.agent_id,
        )

        if gateway_config is not None:
            await dispatch.send_agent_message(
                session_key=session_key,
                config=gateway_config,
                agent_name=MissionSubagentIdentity.label(subtask),
                message=_build_subtask_message(mission=mission, subtask=subtask),
                deliver=True,
            )
        return subtask

    async def dispatch_subtasks_for_mission(self, mission: Mission) -> list[MissionSubtask]:
        subtasks = list(
            (
                await self.session.exec(
                    select(MissionSubtask)
                    .where(MissionSubtask.mission_id == mission.id)
                    .order_by(MissionSubtask.order),
                )
            ).all()
        )
        if not subtasks:
            return []

        for subtask in subtasks:
            await self.dispatch_subtask(mission, subtask)
        return subtasks
