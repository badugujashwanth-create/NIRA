from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from nira.core.text_utils import tokenize_terms


class ErrorMemory:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def record_execution(self, execution) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            for result in execution.results:
                if result.ok:
                    continue
                conn.execute(
                    "INSERT INTO error_memory(task_name, output_text, repaired) VALUES (?, ?, ?)",
                    (execution.current_task or "unknown", result.output, 1 if execution.success else 0),
                )
            conn.commit()

    def search(self, query: str) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        tokens = tokenize_terms(query, min_length=2)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT task_name, output_text, repaired FROM error_memory ORDER BY id DESC LIMIT 20"):
                score = sum(1 for token in tokens if token in row["output_text"].lower())
                if score:
                    results.append(
                        {
                            "task_name": row["task_name"],
                            "output": row["output_text"],
                            "repaired": bool(row["repaired"]),
                            "score": score,
                        }
                    )
        results.sort(key=lambda item: item["score"], reverse=True)
        return results[:5]

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS error_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    output_text TEXT NOT NULL,
                    repaired INTEGER NOT NULL
                )
                """
            )
            conn.commit()
