from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from nira_core.compression.compressor import SemanticCompressor
from nira_core.compression.token_budget import ContextBudgeter
from nira_core.inference import estimate_tokens
from nira_core.retrieval import RetrievalPipeline, RetrievalResult
from nira_core.telemetry import Telemetry


@dataclass(frozen=True, slots=True)
class DistilledContext:
    """Final bounded context used for inference."""

    query: str
    context: str
    context_tokens: int
    retrieval_results: list[RetrievalResult] = field(default_factory=list)


class ContextDistillationPipeline:
    """retrieve -> rerank -> compress -> synthesize with a hard token cap."""

    def __init__(
        self,
        retrieval: RetrievalPipeline,
        compressor: SemanticCompressor,
        budgeter: ContextBudgeter,
        telemetry: Telemetry,
    ) -> None:
        self._retrieval = retrieval
        self._compressor = compressor
        self._budgeter = budgeter
        self._telemetry = telemetry

    async def build_context(
        self,
        query: str,
        reserved_prompt_tokens: int = 80,
        max_final_tokens: int | None = None,
    ) -> DistilledContext:
        """Build a final context never exceeding the configured budget."""

        results = await self._retrieval.retrieve(query)
        results = self._dedupe_results(results)
        raw_context = self._synthesize(results)
        raw_context = self._trim_raw_context(raw_context, max_tokens=1_000)
        compressed = await self._compressor.compress(query, raw_context)
        budgeter = ContextBudgeter(max_final_tokens) if max_final_tokens is not None else self._budgeter
        budgeted = budgeter.trim(compressed.text, reserved_tokens=reserved_prompt_tokens)
        context_tokens = estimate_tokens(budgeted.text)
        prompt_cost_tokens = context_tokens + reserved_prompt_tokens
        self._telemetry.gauge("final_context_tokens", context_tokens)
        self._telemetry.gauge("prompt_cost_estimate_tokens", prompt_cost_tokens)
        self._telemetry.emit(
            "distillation.finish",
            {
                "retrieved": len(results),
                "final_context_tokens": context_tokens,
                "max_tokens": budgeter.max_tokens,
                "prompt_cost_estimate_tokens": prompt_cost_tokens,
            },
        )
        return DistilledContext(
            query=query,
            context=budgeted.text,
            context_tokens=context_tokens,
            retrieval_results=results,
        )

    def _synthesize(self, results: list[RetrievalResult]) -> str:
        chunks: list[str] = []
        for index, result in enumerate(results, start=1):
            chunks.append(f"[{index} score={result.score:.3f} source={result.source}] {result.text}")
        return "\n".join(chunks)

    def _dedupe_results(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        seen: set[str] = set()
        seen_token_sets: list[set[str]] = []
        output: list[RetrievalResult] = []
        for result in results:
            normalized = " ".join(result.text.lower().split())
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            tokens = _token_set(normalized)
            if any(_overlap(tokens, existing) >= 0.88 for existing in seen_token_sets):
                continue
            seen.add(fingerprint)
            if tokens:
                seen_token_sets.append(tokens)
            output.append(result)
        if len(output) != len(results):
            self._telemetry.increment("context_duplicate_chunks_removed_total", len(results) - len(output))
        return output

    def _trim_raw_context(self, context: str, max_tokens: int) -> str:
        tokens = estimate_tokens(context)
        if tokens <= max_tokens:
            return context
        words = context.split()
        accepted: list[str] = []
        for word in words:
            candidate = " ".join([*accepted, word])
            if estimate_tokens(candidate) > max_tokens:
                break
            accepted.append(word)
        self._telemetry.increment("raw_context_truncations_total")
        return " ".join(accepted)


def _token_set(text: str) -> set[str]:
    return {token for token in text.split() if len(token) > 2}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))
