"""Prompt templates for mission decomposition."""

from __future__ import annotations

from app.models.missions import Mission
from app.services.openclaw.context.loader import ContextChunk

def build_decompose_prompt(*, mission: Mission, context: list[ContextChunk]) -> str:
    """Return a deterministic prompt for LLM-based mission decomposition."""
    context_preview = "\n".join(
        f"- [{chunk.source}] {chunk.content[:240].replace(chr(10), ' ')}" for chunk in context[:6]
    )
    constraints = mission.constraints or {}
    return (
        "You are decomposing a mission into executable subtasks for an AI agent swarm.\n"
        "Return JSON only, no markdown.\n"
        "JSON schema:\n"
        '{ "subtasks": [ { "label": str, "description": str, "tool_scope": [str], "expected_output": str } ] }\n'
        f"Mission goal: {mission.goal}\n"
        f"Mission constraints: {constraints}\n"
        f"Context count: {len(context)}\n"
        f"Context preview:\n{context_preview}\n"
        "Ensure subtasks are ordered logically and concise."
    )
