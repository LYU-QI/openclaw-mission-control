"""Notification dispatch service for Feishu bot and webhook channels."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.notifications import NotificationConfig, NotificationLog

logger = logging.getLogger(__name__)


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

        try:
            if config.channel_type == "feishu_bot":
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

        # Build card message
        event_type = payload.get("event_type", "unknown")
        message = payload.get("message", "")

        card_content = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": self._get_event_title(event_type),
                },
                "template": self._get_event_color(event_type),
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": message,
                    },
                },
            ],
        }

        # Use FeishuClient for bot messaging (no app auth needed for webhook)
        import json as _json
        from urllib.request import Request, urlopen

        data = _json.dumps({
            "msg_type": "interactive",
            "card": card_content,
        }).encode()
        req = Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            return _json.loads(resp.read())  # type: ignore[no-any-return]

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

    @staticmethod
    def _get_event_title(event_type: str) -> str:
        titles: dict[str, str] = {
            "mission_created": "📋 新任务已创建",
            "mission_dispatched": "🚀 任务已下发",
            "mission_started": "⚡ 任务开始执行",
            "mission_completed": "✅ 任务执行完成",
            "mission_failed": "❌ 任务执行失败",
            "approval_requested": "⚠️ 需要人工审批",
            "feishu_sync_pull": "🔄 飞书同步完成",
            "feishu_sync_push": "📤 结果已回写飞书",
        }
        return titles.get(event_type, f"📢 {event_type}")

    @staticmethod
    def _get_event_color(event_type: str) -> str:
        colors: dict[str, str] = {
            "mission_completed": "green",
            "mission_failed": "red",
            "approval_requested": "orange",
        }
        return colors.get(event_type, "blue")

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
            return {"ok": log.status == "sent", "message": log.error_message or "Test sent successfully"}
        except Exception as e:
            return {"ok": False, "message": str(e)}
