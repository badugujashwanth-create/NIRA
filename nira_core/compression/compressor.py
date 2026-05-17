from __future__ import annotations

import re
from dataclasses import dataclass

from nira_core.events import Event, EventBus, EventType
from nira_core.inference import InferenceRequest, estimate_tokens
from nira_core.inference.manager import LocalInferenceManager
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry


@dataclass(frozen=True, slots=True)
class CompressedContext:
    """Compressed context and accounting metadata."""

    text: str
    input_tokens: int
    output_tokens: int
    compression_ratio: float


class SemanticCompressor:
    """Compress retrieved context with Phi-3 when available, otherwise extractively."""

    def __init__(
        self,
        inference: LocalInferenceManager | None,
        telemetry: Telemetry,
        model_alias: str = "compression",
        target_tokens: int = 280,
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._inference = inference
        self._telemetry = telemetry
        self._model_alias = model_alias
        self._target_tokens = target_tokens
        self._state = state
        self._event_bus = event_bus

    async def compress(self, query: str, context: str) -> CompressedContext:
        """Semantically compress context while preserving task-relevant details."""

        input_tokens = estimate_tokens(context)
        target_tokens = self._adaptive_target(input_tokens)
        if input_tokens <= target_tokens:
            return self._finalize(context, input_tokens)
        if self._inference is not None:
            prompt = (
                "Compress the context for the task. Keep only directly relevant facts, identifiers, "
                "constraints, and decisions. Do not add new information.\n\n"
                f"Task:\n{query}\n\nContext:\n{context}\n\nCompressed context:"
            )
            try:
                result = await self._inference.generate(
                    InferenceRequest(
                        prompt=prompt,
                        task_type="compression",
                        model_alias=self._model_alias,
                        max_tokens=target_tokens,
                        temperature=0.0,
                    )
                )
                return self._finalize(result.text, input_tokens)
            except Exception as exc:
                self._telemetry.emit("compression.fallback", {"reason": str(exc)})
        return self._finalize(_extractive_compress(query, context, target_tokens), input_tokens)

    def _finalize(self, text: str, input_tokens: int) -> CompressedContext:
        output_tokens = estimate_tokens(text)
        ratio = output_tokens / max(1, input_tokens)
        if self._state is not None:
            self._state.record_compression(ratio)
        self._telemetry.gauge("compression_ratio", ratio)
        self._telemetry.emit(
            "compression.finish",
            {"input_tokens": input_tokens, "output_tokens": output_tokens, "compression_ratio": ratio},
        )
        if self._event_bus is not None:
            self._event_bus.publish_nowait(
                Event.create(
                    EventType.COMPRESSION_COMPLETED,
                    {"input_tokens": input_tokens, "output_tokens": output_tokens, "compression_ratio": ratio},
                )
        )
        return CompressedContext(text=text.strip(), input_tokens=input_tokens, output_tokens=output_tokens, compression_ratio=ratio)

    def _adaptive_target(self, input_tokens: int) -> int:
        target = self._target_tokens
        if input_tokens > 1_200:
            target = min(target, 220)
        if self._state is not None:
            snapshot = self._state.snapshot()
            if float(snapshot.get("ram_usage_mb", 0.0)) > 11_000:
                target = min(target, 180)
        return max(80, target)


def _extractive_compress(query: str, context: str, target_tokens: int) -> str:
    query_terms = set(re.findall(r"\w+", query.lower()))
    sentences = re.split(r"(?<=[.!?])\s+", context.strip())
    scored: list[tuple[float, str]] = []
    for sentence in sentences:
        terms = set(re.findall(r"\w+", sentence.lower()))
        score = len(query_terms & terms) / max(1, len(query_terms))
        scored.append((score, sentence))
    ordered = [sentence for _, sentence in sorted(scored, key=lambda item: item[0], reverse=True)]
    selected: list[str] = []
    for sentence in ordered:
        candidate = " ".join([*selected, sentence])
        if estimate_tokens(candidate) > target_tokens:
            continue
        selected.append(sentence)
    return " ".join(selected) if selected else " ".join(context.split()[: target_tokens * 2])
