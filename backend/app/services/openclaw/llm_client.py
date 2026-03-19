"""Shared LLM client for OpenClaw services."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.core.config import settings


@dataclass(slots=True)
class LLMResponse:
    """Structured LLM response."""

    content: str
    raw: dict[str, Any]


class LLMClient:
    """Generic LLM client supporting Azure OpenAI and standard OpenAI protocols."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.2,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
        provider: Literal["azure", "openai", "local"] | None = None,
    ):
        self.model = model or settings.llm_model
        self.temperature = temperature
        self.api_key = api_key or settings.llm_api_key
        self.base_url = base_url or settings.llm_base_url
        self.api_version = api_version or settings.llm_api_version
        self.provider = (provider or settings.llm_provider or "openai").strip().lower()

    def is_enabled(self) -> bool:
        """Check if LLM client is properly configured."""
        provider = self.provider
        if provider == "local":
            return bool(self.base_url.strip())
        return bool(self.api_key.strip() and self.base_url.strip())

    def _build_request_payload(self, prompt: str, system_prompt: str = "You produce strict JSON only.") -> dict[str, Any]:
        """Build the request payload for LLM API."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

    def _build_url_and_headers(self, payload: dict[str, Any]) -> tuple[str, dict[str, str]]:
        """Build URL and headers based on provider."""
        base_url = self.base_url.rstrip("/")

        if self.provider == "azure":
            deployment = quote(self.model, safe="")
            url = (
                f"{base_url}/openai/deployments/{deployment}/chat/completions"
                f"?api-version={self.api_version}"
            )
            headers = {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
            return url, headers

        url = f"{base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key.strip():
            headers["Authorization"] = f"Bearer {self.api_key}"
        return url, headers

    async def request(self, prompt: str, system_prompt: str = "You produce strict JSON only.") -> LLMResponse:
        """Send a request to the LLM and return the response."""
        if not self.is_enabled():
            raise RuntimeError("LLM client is not configured. Check API key and base URL.")

        payload = self._build_request_payload(prompt, system_prompt)
        url, headers = self._build_url_and_headers(payload)

        def _call() -> dict[str, Any]:
            req = Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(req, timeout=120) as resp:  # noqa: S310
                body = json.loads(resp.read())
            choices = body.get("choices", [])
            if not isinstance(choices, list) or not choices:
                raise ValueError("LLM response missing choices.")
            message = choices[0].get("message", {})
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("LLM response content is empty.")
            return {"content": content, "raw": body}

        result = await asyncio.to_thread(_call)
        return LLMResponse(content=result["content"], raw=result["raw"])

    async def request_json(self, prompt: str, system_prompt: str = "You produce strict JSON only.") -> dict[str, Any]:
        """Send a request to the LLM and parse the response as JSON."""
        response = await self.request(prompt, system_prompt)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

    async def request_text(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
        """Send a request to the LLM and return the response as plain text."""
        payload = self._build_request_payload(prompt, system_prompt)
        # Remove JSON format constraint for text responses
        payload.pop("response_format", None)
        url, headers = self._build_url_and_headers(payload)

        def _call() -> str:
            req = Request(
                url=url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urlopen(req, timeout=120) as resp:  # noqa: S310
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
