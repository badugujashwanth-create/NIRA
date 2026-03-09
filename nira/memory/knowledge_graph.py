from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

from nira.core.text_utils import tokenize_terms


class KnowledgeGraph:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def add_document(self, source_text: str, response_text: str) -> None:
        source_terms = self._extract_terms(source_text)
        response_terms = self._extract_terms(response_text)
        with closing(sqlite3.connect(self.db_path)) as conn:
            for term in source_terms:
                for target in response_terms[:6]:
                    conn.execute(
                        "INSERT INTO knowledge_graph(entity, relation, target) VALUES (?, ?, ?)",
                        (term, "mentions", target),
                    )
            conn.commit()

    def lookup_terms(self, terms: list[str]) -> list[dict[str, str]]:
        if not terms:
            return []
        results: list[dict[str, str]] = []
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for term in terms[:8]:
                for row in conn.execute(
                    "SELECT entity, relation, target FROM knowledge_graph WHERE entity = ? OR target = ? LIMIT 5",
                    (term, term),
                ):
                    results.append({"entity": row["entity"], "relation": row["relation"], "target": row["target"]})
        return results

    def add_research_entry(
        self,
        topic: str,
        subtopics: list[str],
        concepts: list[str],
        tools: list[str] | None = None,
    ) -> None:
        tools = tools or []
        with closing(sqlite3.connect(self.db_path)) as conn:
            for item in subtopics:
                conn.execute(
                    "INSERT INTO knowledge_graph(entity, relation, target) VALUES (?, ?, ?)",
                    (topic, "has_subtopic", item),
                )
            for item in concepts:
                conn.execute(
                    "INSERT INTO knowledge_graph(entity, relation, target) VALUES (?, ?, ?)",
                    (topic, "has_concept", item),
                )
            for item in tools:
                conn.execute(
                    "INSERT INTO knowledge_graph(entity, relation, target) VALUES (?, ?, ?)",
                    (topic, "uses_tool", item),
                )
            conn.commit()

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    target TEXT NOT NULL
                )
                """
            )
            conn.commit()

    @staticmethod
    def _extract_terms(text: str) -> list[str]:
        terms: list[str] = []
        for token in tokenize_terms(text, min_length=4):
            if token not in terms:
                terms.append(token)
            if len(terms) >= 10:
                break
        return terms
