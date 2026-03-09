from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path


class PerformanceAnalyzer:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._ensure_schema()

    def record(self, label: str, duration_ms: float, ok: bool) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO performance_metrics(label, duration_ms, ok) VALUES (?, ?, ?)",
                (label, float(duration_ms), 1 if ok else 0),
            )
            conn.commit()

    def summary(self) -> dict[str, float]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT COUNT(*), AVG(duration_ms), SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) FROM performance_metrics"
            ).fetchone()
        count = row[0] or 0
        avg_duration = row[1] or 0.0
        ok_count = row[2] or 0
        return {
            "count": float(count),
            "avg_duration_ms": round(avg_duration, 2),
            "success_rate": round(ok_count / count, 3) if count else 0.0,
        }

    def breakdown(self, prefix: str | None = None) -> dict[str, dict[str, float]]:
        query = "SELECT label, COUNT(*), AVG(duration_ms), SUM(CASE WHEN ok = 1 THEN 1 ELSE 0 END) FROM performance_metrics"
        params: tuple[object, ...] = ()
        if prefix:
            query += " WHERE label LIKE ?"
            params = (f"{prefix}%",)
        query += " GROUP BY label"
        with closing(sqlite3.connect(self.db_path)) as conn:
            rows = conn.execute(query, params).fetchall()
        breakdown: dict[str, dict[str, float]] = {}
        for label, count, avg_duration, ok_count in rows:
            total = count or 0
            breakdown[str(label)] = {
                "count": float(total),
                "avg_duration_ms": round(avg_duration or 0.0, 2),
                "success_rate": round((ok_count or 0) / total, 3) if total else 0.0,
            }
        return breakdown

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    label TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    ok INTEGER NOT NULL
                )
                """
            )
            conn.commit()
