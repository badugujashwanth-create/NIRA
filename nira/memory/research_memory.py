from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path

from nira.core.text_utils import tokenize_terms


@dataclass
class ResearchEntry:
    topic: str
    summary: str
    concepts: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    report_path: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "concepts": list(self.concepts),
            "references": list(self.references),
            "report_path": self.report_path,
        }


class ResearchMemory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def store(self, entry: ResearchEntry) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO research_memory(topic, summary, concepts_json, references_json, report_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.topic,
                    entry.summary,
                    json.dumps(entry.concepts, ensure_ascii=True),
                    json.dumps(entry.references, ensure_ascii=True),
                    entry.report_path,
                ),
            )
            conn.commit()

    def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        tokens = set(tokenize_terms(query, min_length=2))
        results: list[dict[str, object]] = []
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                "SELECT topic, summary, concepts_json, references_json, report_path FROM research_memory ORDER BY id DESC"
            ):
                try:
                    concepts = json.loads(row["concepts_json"])
                    references = json.loads(row["references_json"])
                except json.JSONDecodeError:
                    concepts = []
                    references = []
                haystack = " ".join([row["topic"], row["summary"], " ".join(concepts)]).lower()
                score = sum(1 for token in tokens if token in haystack)
                if score == 0 and tokens:
                    continue
                results.append(
                    {
                        "topic": row["topic"],
                        "summary": row["summary"],
                        "concepts": concepts,
                        "references": references,
                        "report_path": row["report_path"],
                        "score": score if tokens else 1,
                    }
                )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:limit]

    def latest(self, limit: int = 10) -> list[dict[str, object]]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT topic, summary, concepts_json, references_json, report_path FROM research_memory ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "topic": row["topic"],
                "summary": row["summary"],
                "concepts": _safe_json_list(row["concepts_json"]),
                "references": _safe_json_list(row["references_json"]),
                "report_path": row["report_path"],
            }
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS research_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    concepts_json TEXT NOT NULL,
                    references_json TEXT NOT NULL,
                    report_path TEXT NOT NULL
                )
                """
            )
            conn.commit()


def _safe_json_list(raw: str) -> list[str]:
    try:
        value = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
