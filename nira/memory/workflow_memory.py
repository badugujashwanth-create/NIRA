from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from nira.core.text_utils import tokenize_terms


class WorkflowMemory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def record_trace(self, trace: list[str], success: bool) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO workflow_memory(normalized_trace, trace_json, success) VALUES (?, ?, ?)",
                (" ".join(trace), json.dumps(trace, ensure_ascii=True), 1 if success else 0),
            )
            conn.commit()

    def search(self, query: str) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        tokens = tokenize_terms(query, min_length=2)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT normalized_trace, trace_json, success FROM workflow_memory ORDER BY id DESC LIMIT 20"):
                normalized = row["normalized_trace"]
                score = sum(1 for token in tokens if token in normalized.lower())
                if score:
                    results.append(
                        {
                            "trace": json.loads(row["trace_json"]) if row["trace_json"] else [],
                            "success": bool(row["success"]),
                            "score": score,
                        }
                    )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:5]

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    normalized_trace TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    success INTEGER NOT NULL
                )
                """
            )
            conn.commit()
