from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from nira_core.retrieval.embedding import EmbeddingProvider


@dataclass(frozen=True, slots=True)
class SemanticDocument:
    """A retrieved semantic memory document."""

    id: str
    text: str
    score: float
    metadata: dict[str, str] = field(default_factory=dict)


class SemanticMemory:
    """ChromaDB-backed semantic memory with deterministic in-memory fallback."""

    def __init__(self, path: Path, embedding_provider: EmbeddingProvider, collection_name: str = "nira_semantic") -> None:
        self._path = path
        self._path.mkdir(parents=True, exist_ok=True)
        self._embedding_provider = embedding_provider
        self._collection_name = collection_name
        self._fallback: dict[str, tuple[str, list[float], dict[str, str]]] = {}
        self._collection = self._create_collection()

    def add(self, document_id: str, text: str, metadata: dict[str, str] | None = None) -> None:
        """Add or update a semantic memory document."""

        metadata = dict(metadata or {})
        metadata.setdefault("created_at", str(time.time()))
        embedding = self._embedding_provider.embed(text)
        if self._collection is None:
            self._fallback[document_id] = (text, embedding, metadata)
            return
        self._collection.upsert(ids=[document_id], documents=[text], embeddings=[embedding], metadatas=[metadata])

    def search(self, query: str, limit: int = 8) -> list[SemanticDocument]:
        """Return top semantic matches."""

        query_embedding = self._embedding_provider.embed(query)
        if self._collection is None:
            return self._fallback_search(query_embedding, limit)
        result = self._collection.query(query_embeddings=[query_embedding], n_results=limit)
        ids = result.get("ids", [[]])[0]
        docs = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        items: list[SemanticDocument] = []
        for idx, doc_id in enumerate(ids):
            distance = float(distances[idx]) if idx < len(distances) else 1.0
            items.append(
                SemanticDocument(
                    id=str(doc_id),
                    text=str(docs[idx]),
                    score=1.0 / (1.0 + distance),
                    metadata=dict(metadatas[idx] or {}),
                )
            )
        return items

    def _create_collection(self):
        if os.getenv("NIRA_DISABLE_CHROMA", "").lower() in {"1", "true", "yes", "on"}:
            return None
        try:
            import chromadb
        except ImportError:
            return None
        client = chromadb.PersistentClient(path=str(self._path))
        return client.get_or_create_collection(name=self._collection_name)

    def _fallback_search(self, query_embedding: list[float], limit: int) -> list[SemanticDocument]:
        scored: list[SemanticDocument] = []
        for doc_id, (text, embedding, metadata) in self._fallback.items():
            score = _cosine_similarity(query_embedding, embedding)
            scored.append(SemanticDocument(id=doc_id, text=text, score=score, metadata=metadata))
        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    width = min(len(left), len(right))
    dot = sum(left[i] * right[i] for i in range(width))
    left_norm = math.sqrt(sum(value * value for value in left[:width]))
    right_norm = math.sqrt(sum(value * value for value in right[:width]))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
