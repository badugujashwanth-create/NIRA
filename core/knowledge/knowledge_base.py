from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _embed(text: str, dimensions: int = 128) -> list[float]:
    vector = [0.0] * dimensions
    for token in _tokenize(text):
        index = hash(token) % dimensions
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


@dataclass(slots=True)
class KnowledgeEntry:
    topic: str
    content: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)


class KnowledgeBase:
    def __init__(self, storage_path: str | Path) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = self._load()

    def add(self, *, topic: str, content: str, source: str, metadata: dict[str, Any] | None = None) -> KnowledgeEntry:
        entry = KnowledgeEntry(
            topic=topic.strip(),
            content=content.strip(),
            source=source.strip(),
            metadata=metadata or {},
            embedding=_embed(f"{topic} {content}"),
        )
        self._entries.append(entry)
        self._persist()
        return entry

    def search(self, query: str, limit: int = 3) -> list[KnowledgeEntry]:
        query_vector = _embed(query)
        query_tokens = set(_tokenize(query))
        scored = [
            (
                _cosine_similarity(query_vector, entry.embedding)
                + self._token_overlap_score(query_tokens, entry)
                + self._exact_match_score(query.lower(), entry),
                entry,
            )
            for entry in self._entries
            if entry.content or entry.topic
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for score, entry in scored[: max(1, limit)] if score > 0]

    def all(self) -> list[KnowledgeEntry]:
        return list(self._entries)

    def _load(self) -> list[KnowledgeEntry]:
        if not self.storage_path.exists():
            return []
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        entries: list[KnowledgeEntry] = []
        for item in payload if isinstance(payload, list) else []:
            if not isinstance(item, dict):
                continue
            entries.append(
                KnowledgeEntry(
                    topic=str(item.get("topic", "")),
                    content=str(item.get("content", "")),
                    source=str(item.get("source", "")),
                    metadata=item.get("metadata", {}) if isinstance(item.get("metadata", {}), dict) else {},
                    embedding=[float(value) for value in item.get("embedding", [])],
                )
            )
        return entries

    def _persist(self) -> None:
        serialized = [asdict(entry) for entry in self._entries]
        self.storage_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    @staticmethod
    def _token_overlap_score(query_tokens: set[str], entry: KnowledgeEntry) -> float:
        entry_tokens = set(_tokenize(f"{entry.topic} {entry.content}"))
        if not query_tokens or not entry_tokens:
            return 0.0
        overlap = len(query_tokens & entry_tokens)
        return overlap / max(len(query_tokens), 1)

    @staticmethod
    def _exact_match_score(query: str, entry: KnowledgeEntry) -> float:
        haystack = f"{entry.topic} {entry.content}".lower()
        return 1.0 if any(token and token in haystack for token in query.split()) else 0.0
