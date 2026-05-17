from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Protocol

from nira_core.config import ModelSpec


_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def estimate_tokens(text: str) -> int:
    """Estimate tokens cheaply without loading a tokenizer."""

    if not text:
        return 0
    lexical = len(_TOKEN_RE.findall(text))
    char_estimate = max(1, len(text) // 4)
    return max(lexical, char_estimate)


@dataclass(frozen=True, slots=True)
class TokenAccounting:
    """Prompt and completion token estimates for observability."""

    prompt_tokens: int
    completion_tokens: int
    context_window: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """A generation request routed to one local model."""

    prompt: str
    task_type: str = "general"
    model_alias: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InferenceResult:
    """Text generation result with timing and token estimates."""

    text: str
    model_alias: str
    provider: str
    duration_sec: float
    token_accounting: TokenAccounting
    raw: dict[str, object] = field(default_factory=dict)

    @property
    def tokens_per_sec(self) -> float:
        if self.duration_sec <= 0:
            return 0.0
        return self.token_accounting.completion_tokens / self.duration_sec


class InferenceBackend(Protocol):
    """Backend protocol shared by Ollama and llama.cpp adapters."""

    async def generate(self, spec: ModelSpec, request: InferenceRequest) -> InferenceResult:
        """Generate text for a model spec."""

    async def unload(self, spec: ModelSpec) -> None:
        """Release a loaded model where the backend supports it."""


def result_from_text(
    text: str,
    spec: ModelSpec,
    prompt: str,
    started: float,
    raw: dict[str, object] | None = None,
) -> InferenceResult:
    """Build an inference result with consistent token accounting."""

    return InferenceResult(
        text=text,
        model_alias=spec.alias,
        provider=spec.provider,
        duration_sec=max(0.0, time.perf_counter() - started),
        token_accounting=TokenAccounting(
            prompt_tokens=estimate_tokens(prompt),
            completion_tokens=estimate_tokens(text),
            context_window=spec.context_window,
        ),
        raw=raw or {},
    )
