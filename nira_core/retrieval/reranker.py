from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RerankItem:
    """Text and score pair used during reranking."""

    text: str
    score: float
    metadata: dict[str, str]


class BGEReranker:
    """BGE reranker wrapper with lexical fallback for offline tests."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        self.model_name = model_name
        self._model = None

    def rerank(self, query: str, items: list[RerankItem], limit: int) -> list[RerankItem]:
        """Rerank candidate documents by relevance."""

        model = self._load_model()
        if model is None:
            return sorted(
                (RerankItem(item.text, item.score + _lexical_score(query, item.text), item.metadata) for item in items),
                key=lambda item: item.score,
                reverse=True,
            )[:limit]
        pairs = [[query, item.text] for item in items]
        scores = model.predict(pairs)
        reranked = [
            RerankItem(item.text, float(scores[index]), item.metadata)
            for index, item in enumerate(items)
        ]
        return sorted(reranked, key=lambda item: item.score, reverse=True)[:limit]

    def _load_model(self):
        if self._model is False:
            return None
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            self._model = False
            return None
        self._model = CrossEncoder(self.model_name, device="cpu")
        return self._model


def _lexical_score(query: str, text: str) -> float:
    query_terms = set(re.findall(r"\w+", query.lower()))
    text_terms = set(re.findall(r"\w+", text.lower()))
    if not query_terms:
        return 0.0
    return len(query_terms & text_terms) / len(query_terms)
