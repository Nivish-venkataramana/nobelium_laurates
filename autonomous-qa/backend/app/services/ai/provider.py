"""Abstract LLM provider interface.

Every AI-backed service in the platform depends on this interface, not
on a concrete provider SDK. Swapping providers means writing one new
class; nothing else in the codebase should ever import a provider SDK
directly.

Hard boundary: implementations may only return structured data (dicts /
JSON strings for the caller to validate). They must never execute code,
run shell commands, or touch the database. The LLM proposes; the caller
validates and the execution engine decides.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AICallResult:
    """Uniform result envelope returned by every provider call."""

    raw_text: str
    model: str
    latency_ms: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    estimated_cost_usd: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract provider. Concrete implementations wrap a specific LLM API."""

    name: str = "abstract"

    @abstractmethod
    async def generate_test_plan(
        self, *, application_model: dict, max_tests: int, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        """Ask the model to produce a JSON test plan for an ApplicationModel."""
        raise NotImplementedError

    @abstractmethod
    async def analyze_failure(
        self, *, context: dict, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        """Ask the model to explain why a test failed, in plain language."""
        raise NotImplementedError

    @abstractmethod
    async def suggest_healing(
        self, *, context: dict, system_prompt: str, task_prompt: str
    ) -> AICallResult:
        """Ask the model to recommend which DOM candidate replaces a broken locator."""
        raise NotImplementedError
