"""Agent invocation service - calls OpenClaw agents via Gateway RPC."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlmodel import select

from app.models.agents import Agent
from app.models.gateways import Gateway
from app.services.openclaw.gateway_resolver import gateway_client_config
from app.services.openclaw.gateway_rpc import (
    GatewayConfig,
    ensure_session,
    send_message,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class AgentInvoker:
    """Service for invoking OpenClaw agents via Gateway RPC.

    This service allows Mission Control to invoke OpenClaw agents by sending
    messages to their sessions via the Gateway RPC interface.
    """

    def __init__(self, session: "AsyncSession") -> None:
        """Initialize with database session."""
        self.session = session

    async def invoke_agent(
        self,
        agent_id: UUID,
        instruction: str,
    ) -> dict[str, Any]:
        """Invoke an agent with an instruction (non-blocking).

        This sends the instruction to the agent's session and returns immediately.
        The agent will process the instruction asynchronously.

        Args:
            agent_id: The ID of the agent to invoke
            instruction: The instruction to send to the agent

        Returns:
            Dict with keys: success (bool), session_key (str), error (str)
        """
        # Get agent and its gateway
        agent = await self._get_agent(agent_id)
        if not agent:
            return {"success": False, "session_key": None, "error": f"Agent {agent_id} not found"}

        gateway = await self._get_gateway(agent.gateway_id)
        if not gateway or not gateway.url:
            return {
                "success": False,
                "session_key": None,
                "error": f"Gateway not found for agent {agent_id}",
            }

        config = gateway_client_config(gateway)
        session_key = agent.openclaw_session_id

        if not session_key:
            return {
                "success": False,
                "session_key": None,
                "error": f"Agent {agent_id} has no session key",
            }

        try:
            # Ensure session exists
            await ensure_session(session_key, config=config, label=agent.name)

            # Send message to agent and wait for response
            result = await send_message(
                instruction,
                session_key=session_key,
                config=config,
                deliver=True,  # Wait for agent to complete
            )

            logger.info(
                "agent.invoked agent_id=%s agent_name=%s session_key=%s",
                agent_id,
                agent.name,
                session_key,
            )

            return {"success": True, "session_key": session_key, "error": None, "response": result}

        except Exception as e:
            logger.exception("Failed to invoke agent %s: %s", agent_id, e)
            return {"success": False, "session_key": None, "error": str(e)}

    async def invoke_system_agent(
        self,
        organization_id: UUID,
        system_role: str,
        instruction: str,
    ) -> dict[str, Any]:
        """Invoke a system agent (orchestrator, sync_agent, comms_agent).

        Args:
            organization_id: The organization ID
            system_role: The system role (orchestrator, sync_agent, comms_agent)
            instruction: The instruction to send to the agent

        Returns:
            Dict with keys: success (bool), session_key (str), error (str)
        """
        # Find the system agent via gateway
        stmt = (
            select(Agent, Gateway)
            .join(Gateway, Agent.gateway_id == Gateway.id)
            .where(Agent.system_role == system_role)
            .where(Gateway.organization_id == organization_id)
        )
        result = await self.session.execute(stmt)
        row = result.first()

        if not row:
            agent, gateway = row
            logger.warning(
                "agent_invoker.system_agent_not_found org_id=%s role=%s",
                organization_id,
                system_role,
            )
            return {
                "success": False,
                "session_key": None,
                "error": f"System agent {system_role} not found for org {organization_id}",
            }

        agent, gateway = row
        return await self.invoke_agent(agent.id, instruction)

    async def _get_agent(self, agent_id: UUID) -> Agent | None:
        """Get agent by ID."""
        return await Agent.objects.by_id(agent_id).first(self.session)

    async def _get_gateway(self, gateway_id: UUID) -> Gateway | None:
        """Get gateway by ID."""
        return await Gateway.objects.by_id(gateway_id).first(self.session)
