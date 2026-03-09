from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from pathlib import Path

from nira.core.text_utils import tokenize_terms


class VectorStore:
    def __init__(self, db_path: Path, model, top_k: int = 5) -> None:
        self.db_path = Path(db_path)
        self.model = model
        self.top_k = top_k
        self._ensure_schema()

    def add_text(self, kind: str, text: str, metadata: dict[str, object] | None = None) -> None:
        metadata = metadata or {}
        embedding = self.model.embed_text(text) if self.model else None
        lexical = sorted(set(tokenize_terms(text, min_length=2)))
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO vector_store(kind, text_value, metadata_json, embedding_json, lexical_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    kind,
                    text,
                    json.dumps(metadata, ensure_ascii=True),
                    json.dumps(embedding, ensure_ascii=True) if embedding else None,
                    json.dumps(lexical, ensure_ascii=True),
                ),
            )
            conn.commit()

    def search(self, query: str) -> list[dict[str, object]]:
        query_embedding = self.model.embed_text(query) if self.model else None
        query_terms = set(tokenize_terms(query, min_length=2))
        rows: list[dict[str, object]] = []
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT kind, text_value, metadata_json, embedding_json, lexical_json FROM vector_store"):
                score = 0.0
                embedding_json = row["embedding_json"]
                try:
                    lexical_terms = set(json.loads(row["lexical_json"]))
                    metadata = json.loads(row["metadata_json"])
                    stored_embedding = json.loads(embedding_json) if embedding_json else []
                except json.JSONDecodeError:
                    lexical_terms = set()
                    metadata = {}
                    stored_embedding = []
                if query_embedding and stored_embedding:
                    score = self._cosine(query_embedding, stored_embedding)
                else:
                    overlap = len(query_terms & lexical_terms)
                    score = overlap / max(1, len(query_terms | lexical_terms))
                rows.append(
                    {
                        "kind": row["kind"],
                        "text": row["text_value"],
                        "metadata": metadata,
                        "score": round(score, 4),
                    }
                )
        rows.sort(key=lambda item: item["score"], reverse=True)
        return rows[: self.top_k]

    def add_research_summary(
        self,
        topic: str,
        summary: str,
        concepts: list[str],
        references: list[str],
    ) -> None:
        payload = "\n".join(
            [
                f"Topic: {topic}",
                f"Summary: {summary}",
                f"Concepts: {', '.join(concepts)}",
                f"References: {', '.join(references)}",
            ]
        ).strip()
        self.add_text(
            "research_summary",
            payload,
            {
                "topic": topic,
                "concepts": concepts,
                "references": references,
            },
        )

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_store (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    text_value TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    embedding_json TEXT,
                    lexical_json TEXT NOT NULL
                )
                """
            )
            conn.commit()
