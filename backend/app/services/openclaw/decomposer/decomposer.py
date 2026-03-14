"""Mission task decomposition service."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import settings
from app.models.missions import Mission
from app.services.openclaw.context.loader import ContextChunk
from app.services.openclaw.decomposer.templates import build_decompose_prompt
from app.services.openclaw.decomposer.validator import validate_subtasks


@dataclass(slots=True)
class SubtaskSpec:
    """Structured decomposition item."""

    label: str
    description: str
    tool_scope: list[str]
    expected_output: str
    order: int


class TaskDecomposer:
    """Creates subtasks from mission goal and loaded context."""

    def _fallback_subtasks(
        self, *, mission: Mission, context: list[ContextChunk]
    ) -> list[dict[str, Any]]:
        context_desc = f"Review {len(context)} context chunks and extract facts."
        if not context:
            context_desc = "No context provided; identify assumptions and missing inputs."
        return [
            {
                "label": "Gather Facts",
                "description": context_desc,
                "tool_scope": ["context_loader", "analysis"],
                "expected_output": "A concise list of confirmed facts and unknowns.",
            },
            {
                "label": "Analyze Options",
                "description": f"Analyze tradeoffs to satisfy goal: {mission.goal[:220]}",
                "tool_scope": ["analysis"],
                "expected_output": "Recommendation with risks and confidence.",
            },
            {
                "label": "Prepare Execution Plan",
                "description": "Draft actionable next steps with owners and sequencing.",
                "tool_scope": ["analysis"],
                "expected_output": "Ordered execution checklist with dependencies.",
            },
        ]

    def _llm_enabled(self) -> bool:
        provider = settings.llm_provider.strip().lower()
        if provider == "local":
            return bool(settings.llm_base_url.strip())
        return bool(settings.llm_api_key.strip() and settings.llm_base_url.strip())

    def _build_provider_request(self, prompt: str) -> tuple[str, dict[str, str], dict[str, Any]]:
        provider = settings.llm_provider.strip().lower()
        base_url = settings.llm_base_url.rstrip("/")
        payload = {
            "model": settings.llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You produce strict JSON only."},
                {"role": "user", "content": prompt},
            ],
        }

        if provider == "azure":
            deployment = quote(settings.llm_model, safe="")
            url = (
                f"{base_url}/openai/deployments/{deployment}/chat/completions"
                f"?api-version={settings.llm_api_version}"
            )
            headers = {
                "Content-Type": "application/json",
                "api-key": settings.llm_api_key,
            }
            return url, headers, payload

        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key.strip():
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"
        return url, headers, payload

    async def _request_llm(self, prompt: str) -> str:
        url, headers, payload = self._build_provider_request(prompt)

        def _call() -> str:
            req = Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(
                req, timeout=max(settings.context_loader_timeout_seconds, 5)
            ) as resp:  # noqa: S310
                body = json.loads(resp.read())
            choices = body.get("choices", [])
            if not isinstance(choices, list) or not choices:
                raise ValueError("LLM response missing choices.")
            message = choices[0].get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("LLM response content is empty.")
            return content

        return await asyncio.to_thread(_call)

    def _parse_llm_subtasks(self, raw: str) -> list[dict[str, Any]]:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
        if isinstance(parsed, dict):
            subtasks = parsed.get("subtasks")
            if isinstance(subtasks, list):
                return [item for item in subtasks if isinstance(item, dict)]
        raise ValueError("Unsupported LLM subtask payload format.")

    async def decompose(
        self, *, mission: Mission, context: list[ContextChunk]
    ) -> list[SubtaskSpec]:
        candidate: list[dict[str, Any]] = self._fallback_subtasks(mission=mission, context=context)
        if self._llm_enabled():
            prompt = build_decompose_prompt(mission=mission, context=context)
            try:
                llm_raw = await self._request_llm(prompt)
                candidate = self._parse_llm_subtasks(llm_raw)
            except Exception:
                candidate = self._fallback_subtasks(mission=mission, context=context)

        valid = validate_subtasks(candidate)
        if not valid:
            valid = validate_subtasks(self._fallback_subtasks(mission=mission, context=context))

        return [
            SubtaskSpec(
                label=str(item["label"]),
                description=str(item["description"]),
                tool_scope=list(item.get("tool_scope", [])),
                expected_output=str(item.get("expected_output", "")),
                order=index,
            )
            for index, item in enumerate(valid)
        ]
