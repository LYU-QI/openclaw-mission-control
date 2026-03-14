"""Agent key derivation helpers shared across OpenClaw modules."""

from __future__ import annotations

import re
from uuid import uuid4

from app.models.agents import Agent
from app.services.openclaw.constants import _SESSION_KEY_PARTS_MIN


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or uuid4().hex


def agent_key(agent: Agent) -> str:
    """Return stable gateway agent id derived from session key or name fallback.
    
    System agents (orchestrator, sync, etc.) use a specific deterministic ID
    regardless of their display name to ensure consistency across gateways.
    """
    session_key = agent.openclaw_session_id or ""
    if session_key.startswith("agent:"):
        parts = session_key.split(":")
        if len(parts) >= _SESSION_KEY_PARTS_MIN and parts[1]:
            return parts[1]
    
    # If this is a system-role agent without a standard agent: session key,
    # we use a deterministic key based on the gateway and role.
    if agent.system_role and agent.gateway_id:
        from app.services.openclaw.shared import GatewayAgentIdentity
        # We need a partial gateway object or at least the ID
        from app.models.gateways import Gateway
        fake_gateway = Gateway(id=agent.gateway_id)
        return GatewayAgentIdentity.system_agent_id(fake_gateway, agent.system_role)

    return slugify(agent.name)
