"""Gateway session query service."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status

from app.core.logging import TRACE_LEVEL
from app.models.boards import Board
from app.models.gateways import Gateway
from app.schemas.gateway_api import (
    GatewayHealthLayer,
    GatewayHealthLayers,
    GatewayResolveQuery,
    GatewaySessionHistoryResponse,
    GatewaySessionMessageRequest,
    GatewaySessionResponse,
    GatewaySessionsResponse,
    GatewaysStatusResponse,
)
from app.services.openclaw.db_service import OpenClawDBService
from app.services.openclaw.error_messages import (
    classify_gateway_error_message,
    normalize_gateway_error_message,
)
from app.services.openclaw.gateway_compat import check_gateway_version_compatibility
from app.services.openclaw.gateway_resolver import gateway_client_config, require_gateway_for_board
from app.services.openclaw.gateway_rpc import GatewayConfig as GatewayClientConfig
from app.services.openclaw.gateway_rpc import (
    OpenClawGatewayError,
    ensure_session,
    get_chat_history,
    openclaw_call,
    send_message,
)
from app.services.openclaw.policies import OpenClawAuthorizationPolicy
from app.services.openclaw.shared import GatewayAgentIdentity
from app.services.organizations import require_board_access

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.users import User


@dataclass(frozen=True, slots=True)
class GatewayTemplateSyncQuery:
    """Sync options parsed from query args for gateway template operations."""

    include_main: bool
    lead_only: bool
    reset_sessions: bool
    rotate_tokens: bool
    force_bootstrap: bool
    overwrite: bool
    board_id: UUID | None


class GatewaySessionService(OpenClawDBService):
    """Read/query gateway runtime session state for user-facing APIs."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    @staticmethod
    def _layer(ok: bool, label: str, detail: str | None = None) -> GatewayHealthLayer:
        return GatewayHealthLayer(ok=ok, label=label, detail=detail)

    @classmethod
    def _layers(
        cls,
        *,
        http_reachable: GatewayHealthLayer,
        ws_handshake: GatewayHealthLayer,
        rpc_ready: GatewayHealthLayer,
        session_visible: GatewayHealthLayer,
        main_agent_checkin: GatewayHealthLayer,
    ) -> GatewayHealthLayers:
        return GatewayHealthLayers(
            http_reachable=http_reachable,
            ws_handshake=ws_handshake,
            rpc_ready=rpc_ready,
            session_visible=session_visible,
            main_agent_checkin=main_agent_checkin,
        )

    @staticmethod
    def to_resolve_query(
        board_id: str | None,
        gateway_url: str | None,
        gateway_token: str | None,
        gateway_disable_device_pairing: bool | None = None,
        gateway_allow_insecure_tls: bool | None = None,
    ) -> GatewayResolveQuery:
        return GatewayResolveQuery(
            board_id=board_id,
            gateway_url=gateway_url,
            gateway_token=gateway_token,
            gateway_disable_device_pairing=gateway_disable_device_pairing,
            gateway_allow_insecure_tls=gateway_allow_insecure_tls,
        )

    @staticmethod
    def as_object_list(value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, (tuple, set)):
            return list(value)
        if isinstance(value, (str, bytes, dict)):
            return []
        if isinstance(value, Iterable):
            return list(value)
        return []

    async def resolve_gateway(
        self,
        params: GatewayResolveQuery,
        *,
        user: User | None = None,
        organization_id: UUID | None = None,
    ) -> tuple[Board | None, GatewayClientConfig, str | None]:
        self.logger.log(
            TRACE_LEVEL,
            "gateway.resolve.start board_id=%s gateway_url=%s",
            params.board_id,
            params.gateway_url,
        )
        if params.gateway_url:
            raw_url = params.gateway_url.strip()
            if not raw_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="board_id or gateway_url is required",
                )
            token = (params.gateway_token or "").strip() or None
            gateway: Gateway | None = None
            can_query_saved_gateway = organization_id is not None and hasattr(self.session, "exec")
            if can_query_saved_gateway and (
                params.gateway_allow_insecure_tls is None
                or params.gateway_disable_device_pairing is None
            ):
                gateway_query = Gateway.objects.filter_by(url=raw_url)
                if organization_id is not None:
                    gateway_query = gateway_query.filter_by(organization_id=organization_id)
                gateway = await gateway_query.first(self.session)
            allow_insecure_tls = (
                params.gateway_allow_insecure_tls
                if params.gateway_allow_insecure_tls is not None
                else (gateway.allow_insecure_tls if gateway is not None else False)
            )
            disable_device_pairing = (
                params.gateway_disable_device_pairing
                if params.gateway_disable_device_pairing is not None
                else (gateway.disable_device_pairing if gateway is not None else False)
            )
            return (
                None,
                GatewayClientConfig(
                    url=raw_url,
                    token=token,
                    allow_insecure_tls=allow_insecure_tls,
                    disable_device_pairing=disable_device_pairing,
                ),
                None,
            )
        if not params.board_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="board_id or gateway_url is required",
            )
        board = await Board.objects.by_id(params.board_id).first(self.session)
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        if user is not None:
            await require_board_access(self.session, user=user, board=board, write=False)
        gateway = await require_gateway_for_board(self.session, board)
        config = gateway_client_config(gateway)
        main_session = GatewayAgentIdentity.session_key(gateway)
        return (
            board,
            config,
            main_session,
        )

    async def require_gateway(
        self,
        board_id: str | None,
        *,
        user: User | None = None,
    ) -> tuple[Board, GatewayClientConfig, str | None]:
        params = GatewayResolveQuery(board_id=board_id)
        board, config, main_session = await self.resolve_gateway(params, user=user)
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="board_id is required",
            )
        return board, config, main_session

    async def list_sessions(self, config: GatewayClientConfig) -> list[dict[str, object]]:
        sessions = await openclaw_call("sessions.list", config=config)
        if isinstance(sessions, dict):
            raw_items = self.as_object_list(sessions.get("sessions"))
        else:
            raw_items = self.as_object_list(sessions)
        return [item for item in raw_items if isinstance(item, dict)]

    async def with_main_session(
        self,
        sessions_list: list[dict[str, object]],
        *,
        config: GatewayClientConfig,
        main_session: str | None,
    ) -> list[dict[str, object]]:
        if not main_session or any(item.get("key") == main_session for item in sessions_list):
            return sessions_list
        try:
            await ensure_session(main_session, config=config, label="Gateway Agent")
            return await self.list_sessions(config)
        except OpenClawGatewayError:
            return sessions_list

    @staticmethod
    def _require_same_org(board: Board | None, organization_id: UUID) -> None:
        if board is None:
            return
        OpenClawAuthorizationPolicy.require_board_write_access(
            allowed=board.organization_id == organization_id,
        )

    async def get_status(
        self,
        *,
        params: GatewayResolveQuery,
        organization_id: UUID,
        user: User | None,
    ) -> GatewaysStatusResponse:
        board, config, main_session = await self.resolve_gateway(
            params,
            user=user,
            organization_id=organization_id,
        )
        self._require_same_org(board, organization_id)
        try:
            compatibility = await check_gateway_version_compatibility(config)
        except OpenClawGatewayError as exc:
            normalized = normalize_gateway_error_message(str(exc))
            info = classify_gateway_error_message(str(exc))
            return GatewaysStatusResponse(
                connected=False,
                gateway_url=config.url,
                error=normalized,
                layers=self._layers(
                    http_reachable=self._layer(
                        info.code != "TRANSPORT_ERROR",
                        "HTTP 可达",
                        None if info.code != "TRANSPORT_ERROR" else normalized,
                    ),
                    ws_handshake=self._layer(False, "WS 握手", normalized),
                    rpc_ready=self._layer(False, "RPC 可调用", normalized),
                    session_visible=self._layer(False, "Session 可见", "尚未进入 session 查询阶段"),
                    main_agent_checkin=self._layer(
                        False, "主 Agent check-in", "尚未进入 check-in 阶段"
                    ),
                ),
            )
        if not compatibility.compatible:
            return GatewaysStatusResponse(
                connected=False,
                gateway_url=config.url,
                error=compatibility.message,
                layers=self._layers(
                    http_reachable=self._layer(True, "HTTP 可达", "已获取运行时元数据"),
                    ws_handshake=self._layer(True, "WS 握手", "已完成连接握手"),
                    rpc_ready=self._layer(False, "RPC 可调用", compatibility.message),
                    session_visible=self._layer(
                        False, "Session 可见", "版本不兼容，未继续查询 session"
                    ),
                    main_agent_checkin=self._layer(
                        False, "主 Agent check-in", "版本不兼容，未继续检查"
                    ),
                ),
            )
        try:
            sessions = await openclaw_call("sessions.list", config=config)
            if isinstance(sessions, dict):
                sessions_list = self.as_object_list(sessions.get("sessions"))
            else:
                sessions_list = self.as_object_list(sessions)
            main_session_entry: object | None = None
            main_session_error: str | None = None
            if main_session:
                try:
                    ensured = await ensure_session(
                        main_session,
                        config=config,
                        label="Gateway Agent",
                    )
                    if isinstance(ensured, dict):
                        main_session_entry = ensured.get("entry") or ensured
                except OpenClawGatewayError as exc:
                    main_session_error = str(exc)
            sessions_count = len(sessions_list)
            main_agent_ok = main_session_error is None
            return GatewaysStatusResponse(
                connected=True,
                gateway_url=config.url,
                sessions_count=sessions_count,
                sessions=sessions_list,
                main_session=main_session_entry,
                main_session_error=main_session_error,
                layers=self._layers(
                    http_reachable=self._layer(True, "HTTP 可达", "已建立到 Gateway 的基础连接"),
                    ws_handshake=self._layer(True, "WS 握手", "已完成 WebSocket 握手"),
                    rpc_ready=self._layer(True, "RPC 可调用", "sessions.list 调用成功"),
                    session_visible=self._layer(
                        sessions_count > 0,
                        "Session 可见",
                        f"当前发现 {sessions_count} 个 session。",
                    ),
                    main_agent_checkin=self._layer(
                        main_agent_ok,
                        "主 Agent check-in",
                        (
                            "主 Agent session 已建立。"
                            if main_agent_ok and main_session_entry is not None
                            else (
                                normalize_gateway_error_message(main_session_error)
                                if main_session_error
                                else "主 Agent 尚未完成 check-in。"
                            )
                        ),
                    ),
                ),
            )
        except OpenClawGatewayError as exc:
            normalized = normalize_gateway_error_message(str(exc))
            return GatewaysStatusResponse(
                connected=False,
                gateway_url=config.url,
                error=normalized,
                layers=self._layers(
                    http_reachable=self._layer(True, "HTTP 可达", "已建立到 Gateway 的基础连接"),
                    ws_handshake=self._layer(True, "WS 握手", "已完成连接握手"),
                    rpc_ready=self._layer(False, "RPC 可调用", normalized),
                    session_visible=self._layer(False, "Session 可见", "RPC 查询失败，无法判断"),
                    main_agent_checkin=self._layer(
                        False, "主 Agent check-in", "RPC 查询失败，无法判断"
                    ),
                ),
            )

    async def get_sessions(
        self,
        *,
        board_id: str | None,
        organization_id: UUID,
        user: User | None,
    ) -> GatewaySessionsResponse:
        params = GatewayResolveQuery(board_id=board_id)
        board, config, main_session = await self.resolve_gateway(params, user=user)
        self._require_same_org(board, organization_id)
        try:
            sessions = await openclaw_call("sessions.list", config=config)
        except OpenClawGatewayError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        if isinstance(sessions, dict):
            sessions_list = self.as_object_list(sessions.get("sessions"))
        else:
            sessions_list = self.as_object_list(sessions)

        main_session_entry: object | None = None
        if main_session:
            try:
                ensured = await ensure_session(
                    main_session,
                    config=config,
                    label="Gateway Agent",
                )
                if isinstance(ensured, dict):
                    main_session_entry = ensured.get("entry") or ensured
            except OpenClawGatewayError:
                main_session_entry = None
        return GatewaySessionsResponse(sessions=sessions_list, main_session=main_session_entry)

    async def get_session(
        self,
        *,
        session_id: str,
        board_id: str | None,
        organization_id: UUID,
        user: User | None,
    ) -> GatewaySessionResponse:
        params = GatewayResolveQuery(board_id=board_id)
        board, config, main_session = await self.resolve_gateway(params, user=user)
        self._require_same_org(board, organization_id)
        try:
            sessions_list = await self.list_sessions(config)
        except OpenClawGatewayError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        sessions_list = await self.with_main_session(
            sessions_list,
            config=config,
            main_session=main_session,
        )
        session_entry = next(
            (item for item in sessions_list if item.get("key") == session_id), None
        )
        if session_entry is None and main_session and session_id == main_session:
            try:
                ensured = await ensure_session(
                    main_session,
                    config=config,
                    label="Gateway Agent",
                )
                if isinstance(ensured, dict):
                    session_entry = ensured.get("entry") or ensured
            except OpenClawGatewayError:
                session_entry = None
        if session_entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )
        return GatewaySessionResponse(session=session_entry)

    async def get_session_history(
        self,
        *,
        session_id: str,
        board_id: str | None,
        organization_id: UUID,
        user: User | None,
    ) -> GatewaySessionHistoryResponse:
        board, config, _ = await self.require_gateway(board_id, user=user)
        self._require_same_org(board, organization_id)
        try:
            history = await get_chat_history(session_id, config=config)
        except OpenClawGatewayError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        if isinstance(history, dict) and isinstance(history.get("messages"), list):
            return GatewaySessionHistoryResponse(history=history["messages"])
        return GatewaySessionHistoryResponse(history=self.as_object_list(history))

    async def send_session_message(
        self,
        *,
        session_id: str,
        payload: GatewaySessionMessageRequest,
        board_id: str | None,
        user: User | None,
    ) -> None:
        board, config, main_session = await self.require_gateway(board_id, user=user)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        await require_board_access(self.session, user=user, board=board, write=True)
        try:
            if main_session and session_id == main_session:
                await ensure_session(main_session, config=config, label="Gateway Agent")
            await send_message(payload.content, session_key=session_id, config=config)
        except OpenClawGatewayError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
