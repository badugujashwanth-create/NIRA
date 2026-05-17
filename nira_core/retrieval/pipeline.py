from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

from nira_core.events import Event, EventBus, EventType
from nira_core.memory import MemoryManager
from nira_core.retrieval.reranker import BGEReranker, RerankItem
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A retrieved and reranked context candidate."""

    text: str
    score: float
    source: str
    metadata: dict[str, str] = field(default_factory=dict)


class RetrievalPipeline:
    """Retrieve semantic and episodic candidates, then rerank."""

    def __init__(
        self,
        memory: MemoryManager,
        reranker: BGEReranker,
        telemetry: Telemetry,
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._memory = memory
        self._reranker = reranker
        self._telemetry = telemetry
        self._state = state
        self._event_bus = event_bus

    async def retrieve(self, query: str, limit: int = 8) -> list[RetrievalResult]:
        """Retrieve and rerank context candidates."""

        semantic = self._memory.search(query, limit=limit)
        episodic = self._memory.episodic.search(query, limit=max(2, limit // 2))
        candidates = [
            RerankItem(item.text, item.score, {"source": "semantic", **item.metadata})
            for item in semantic
        ]
        candidates.extend(
            RerankItem(item.content, item.importance, {"source": "episodic", "kind": item.kind})
            for item in episodic
        )
        candidates = self._dedupe_candidates(candidates)
        reranked = self._reranker.rerank(query, candidates, limit)
        top_score = reranked[0].score if reranked else 0.0
        if self._state is not None:
            self._state.record_retrieval_precision(top_score)
        self._telemetry.gauge("retrieval_quality_top_score", top_score)
        self._telemetry.emit("retrieval.finish", {"candidates": len(candidates), "returned": len(reranked)})
        if self._event_bus is not None:
            await self._event_bus.publish(
                Event.create(
                    EventType.RETRIEVAL_COMPLETED,
                    {"candidates": len(candidates), "returned": len(reranked), "top_score": top_score},
                )
            )
        return [
            RetrievalResult(
                text=item.text,
                score=item.score,
                source=item.metadata.get("source", "unknown"),
                metadata=item.metadata,
            )
            for item in reranked
        ]

    def _dedupe_candidates(self, candidates: list[RerankItem]) -> list[RerankItem]:
        seen: set[str] = set()
        seen_token_sets: list[set[str]] = []
        output: list[RerankItem] = []
        for item in candidates:
            normalized = " ".join(item.text.lower().split())
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            tokens = _token_set(normalized)
            if any(_overlap(tokens, existing) >= 0.86 for existing in seen_token_sets):
                continue
            seen.add(fingerprint)
            if tokens:
                seen_token_sets.append(tokens)
            output.append(item)
        if len(output) != len(candidates):
            self._telemetry.increment("retrieval_duplicates_removed_total", len(candidates) - len(output))
        return output


def _token_set(text: str) -> set[str]:
    return {token for token in text.split() if len(token) > 2}


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))
