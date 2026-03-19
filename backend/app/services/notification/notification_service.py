"""Notification dispatch service for Feishu bot and webhook channels."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from jinja2 import Environment, FileSystemLoader
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.notifications import NotificationConfig, NotificationLog
from app.services.notification.feishu_bot import send_feishu_webhook
from app.services.notification.templates import build_feishu_card_payload

if TYPE_CHECKING:
    from app.services.openclaw.agent_invoker import AgentInvoker

logger = logging.getLogger(__name__)

# Templates root for agent tasks
def _templates_root():
    from pathlib import Path
    return Path(__file__).resolve().parents[3] / "templates"


def _template_env():
    return Environment(
        loader=FileSystemLoader(_templates_root()),
        autoescape=False,
        keep_trailing_newline=True,
    )


class NotificationService:
    """Dispatches notifications to configured channels."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def notify(
        self,
        *,
        organization_id: UUID,
        event_type: str,
        message: str,
        board_id: UUID | None = None,
        extra: dict[str, Any] | None = None,
    ) -> list[NotificationLog]:
        """Send notifications to all matching configs for an event type."""
        stmt = select(NotificationConfig).where(
            NotificationConfig.organization_id == organization_id,
            NotificationConfig.enabled == True,  # noqa: E712
        )
        result = await self.session.exec(stmt)
        configs = list(result.all())

        logs: list[NotificationLog] = []
        for config in configs:
            # Check if this event type is in the config's notify list
            if config.notify_on_events and event_type not in config.notify_on_events:
                continue

            # Check board scope
            if config.board_id and config.board_id != board_id:
                continue

            log = await self._dispatch(config, event_type, message, extra)
            logs.append(log)

        if logs:
            await self.session.commit()

        return logs

    async def _dispatch(
        self,
        config: NotificationConfig,
        event_type: str,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> NotificationLog:
        """Send a notification via a specific channel."""
        payload: dict[str, Any] = {
            "event_type": event_type,
            "message": message,
            **(extra or {}),
        }

        status = "sent"
        response: dict[str, Any] | None = None
        error_message: str | None = None

        # Check if we should use Agent-based notification
        # This can be enabled via environment variable ENABLE_AGENT_NOTIFICATIONS
        use_agent_notification = settings.enable_agent_notifications

        logger.info(
            "notification.dispatch_check event_type=%s use_agent=%s org_id=%s",
            event_type,
            use_agent_notification,
            config.organization_id,
        )

        try:
            if config.channel_type == "feishu_bot":
                # Try Agent-based notification if enabled
                if use_agent_notification and config.organization_id:
                    agent_result = await self._invoke_comms_agent(
                        config.organization_id,
                        event_type,
                        payload,
                    )
                    if agent_result.get("sent"):
                        # Agent handled it successfully
                        response = agent_result
                    else:
                        # Fall back to direct webhook
                        logger.info(
                            "notification.agent_fallback event_type=%s error=%s",
                            event_type,
                            agent_result.get("error"),
                        )
                        response = self._send_feishu_bot(config.channel_config, payload)
                else:
                    # Direct webhook (default)
                    response = self._send_feishu_bot(config.channel_config, payload)
            elif config.channel_type == "webhook":
                response = self._send_webhook(config.channel_config, payload)
            else:
                error_message = f"Unknown channel type: {config.channel_type}"
                status = "failed"
        except Exception as e:
            logger.exception("Failed to send notification via %s", config.channel_type)
            error_message = str(e)
            status = "failed"

        log = NotificationLog(
            notification_config_id=config.id,
            event_type=event_type,
            channel_type=config.channel_type,
            payload=payload,
            status=status,
            response=response,
            error_message=error_message,
        )
        self.session.add(log)
        return log

    def _send_feishu_bot(
        self,
        channel_config: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a Feishu bot notification via webhook."""
        webhook_url = channel_config.get("webhook_url", "")
        if not webhook_url:
            return {"error": "No webhook_url configured"}

        event_type = payload.get("event_type", "unknown")
        message = payload.get("message", "")
        card_payload = build_feishu_card_payload(
            event_type=str(event_type),
            message=str(message),
            payload=payload,
        )

        response = send_feishu_webhook(
            webhook_url=webhook_url,
            payload=card_payload,
            secret=str(
                channel_config.get("webhook_secret") or settings.feishu_bot_webhook_secret or ""
            ),
        )
        return response

    def _send_webhook(
        self,
        channel_config: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a generic webhook notification."""
        url = channel_config.get("url", "")
        if not url:
            return {"error": "No url configured"}

        import json as _json
        from urllib.request import Request, urlopen

        data = _json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"}
        # Merge any extra headers from config
        extra_headers = channel_config.get("headers", {})
        headers.update(extra_headers)

        req = Request(url, data=data, headers=headers, method="POST")
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            return _json.loads(resp.read())  # type: ignore[no-any-return]

    async def _invoke_comms_agent(
        self,
        organization_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke Comms Agent to send notification via Gateway RPC.

        This is an alternative to direct webhook sending - it calls the Comms Agent
        which then sends the message to the Feishu group.
        """
        try:
            # Import here to avoid circular imports
            from app.services.openclaw.agent_invoker import AgentInvoker

            invoker = AgentInvoker(self.session)

            # Render the task instruction template
            template = _template_env().get_template("agent_tasks/comms_agent_task.md.j2")

            # Extract relevant fields for the template
            instruction = template.render(
                event_type=event_type,
                task_title=payload.get("task_title", ""),
                mission_id=payload.get("mission_id", ""),
                result_summary=payload.get("result_summary", ""),
                risk=payload.get("risk", ""),
                next_action=payload.get("next_action", ""),
                subtask_results=payload.get("subtask_results", ""),
                error_message=payload.get("error_message", ""),
                approval_type=payload.get("approval_type", ""),
                approval_content=payload.get("approval_content", ""),
                approval_url=payload.get("approval_url", ""),
                due_date=payload.get("due_date", ""),
                overdue_days=payload.get("overdue_days", ""),
                reminder_content=payload.get("reminder_content", ""),
                # Format artifact links as a list
                artifact_links=payload.get("artifact_links", []),
            )

            # Invoke the Comms Agent
            result = await invoker.invoke_system_agent(
                organization_id=organization_id,
                system_role="comms_agent",
                instruction=instruction,
            )

            if result.get("success"):
                logger.info("comms_agent.notification_sent event_type=%s", event_type)
                return {"sent": True, "agent_response": result.get("response")}
            else:
                logger.warning(
                    "comms_agent.notification_failed event_type=%s error=%s",
                    event_type,
                    result.get("error"),
                )
                return {"sent": False, "error": result.get("error")}

        except Exception as e:
            logger.exception("Failed to invoke Comms Agent: %s", e)
            return {"sent": False, "error": str(e)}

    async def test_notification(self, config_id: UUID) -> dict[str, Any]:
        """Send a test notification to verify channel configuration."""
        config = await NotificationConfig.objects.by_id(config_id).first(self.session)
        if config is None:
            return {"ok": False, "message": "Config not found"}

        try:
            log = await self._dispatch(
                config,
                event_type="test",
                message="🔔 这是一条测试通知。\n\nMission Control 通知服务已连接成功！",
            )
            await self.session.commit()
            return {
                "ok": log.status == "sent",
                "message": log.error_message or "Test sent successfully",
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}
