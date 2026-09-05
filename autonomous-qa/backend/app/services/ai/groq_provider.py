"""Concrete LLMProvider backed by the Groq API.

This is the ONLY file in the codebase that imports the groq SDK. All
other services depend on the LLMProvider abstraction.
"""
from __future__ import annotations

import time

from groq import AsyncGroq

from app.core.config import get_settings
from app.core.exceptions import AIProviderError
from app.core.logging import get_logger
from app.services.ai.provider import AICallResult, LLMProvider

logger = get_logger(__name__)

# Rough per-token cost estimate for observability only (not billing-accurate).
_ESTIMATED_COST_PER_1K_TOKENS_USD = 0.00059


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self._model = model or settings.GROQ_MODEL
        self._client = AsyncGroq(api_key=api_key or settings.GROQ_API_KEY)
        self._timeout = settings.AI_TIMEOUT_SECONDS

    async def _call(self, system_prompt: str, task_prompt: str) -> AICallResult:
        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("groq.call_failed", error=str(exc))
            raise AIProviderError(f"Groq API call failed: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        choice = response.choices[0]
        text = choice.message.content or ""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
        estimated_cost = (
            (total_tokens / 1000) * _ESTIMATED_COST_PER_1K_TOKENS_USD if total_tokens else None
        )

        return AICallResult(
            raw_text=text,
            model=self._model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost,
            metadata={"request_id": getattr(response, "id", None)},
        )

    async def generate_test_plan(
        self, *, application_model: dict, max_tests: int, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        return await self._call(system_prompt, task_prompt)

    async def analyze_failure(
        self, *, context: dict, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        return await self._call(system_prompt, task_prompt)

    async def suggest_healing(
        self, *, context: dict, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        return await self._call(system_prompt, task_prompt)


def get_llm_provider() -> LLMProvider:
    """Factory used by services. Swapping AI_PROVIDER in config is the
    only change needed to add a new provider once implemented."""
    settings = get_settings()
    if settings.AI_PROVIDER == "groq":
        return GroqProvider()
    raise AIProviderError(f"Unsupported AI_PROVIDER: {settings.AI_PROVIDER}")
