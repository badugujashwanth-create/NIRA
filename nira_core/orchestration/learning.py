from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CachedWorkflow:
    """A reusable workflow result for low-friction repeated tasks."""

    workflow: str
    goal: str
    answer: str
    steps: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    metadata: dict[str, Any]
    success_score: float
    age_seconds: float


class WorkflowLearningStore:
    """Tiny local workflow analytics and cache store.

    The store is intentionally conservative: it only caches successful outputs,
    uses short TTLs, and keeps aggregate usage data in SQLite so daily patterns
    can improve without adding another service.
    """

    def __init__(self, path: Path, cache_ttl_sec: int = 6 * 60 * 60) -> None:
        self._path = path
        self._cache_ttl_sec = cache_ttl_sec
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_cached(self, workflow: str, goal: str) -> CachedWorkflow | None:
        """Return a fresh high-confidence cached workflow result, if present."""

        key = self._cache_key(workflow, goal)
        now = time.time()
        with self._lock, sqlite3.connect(self._path) as db:
            row = db.execute(
                """
                SELECT workflow, goal, answer, steps_json, sources_json, metadata_json,
                       success_score, created_at
                FROM workflow_cache
                WHERE cache_key = ?
                """,
                (key,),
            ).fetchone()
            if row is None:
                return None
            age = now - float(row[7])
            if age > self._cache_ttl_sec or float(row[6]) < 0.72:
                return None
            db.execute(
                "UPDATE workflow_cache SET hit_count = hit_count + 1, last_hit_at = ? WHERE cache_key = ?",
                (now, key),
            )
            return CachedWorkflow(
                workflow=str(row[0]),
                goal=str(row[1]),
                answer=str(row[2]),
                steps=json.loads(row[3] or "[]"),
                sources=json.loads(row[4] or "[]"),
                metadata=json.loads(row[5] or "{}"),
                success_score=float(row[6]),
                age_seconds=age,
            )

    def record(
        self,
        workflow: str,
        goal: str,
        result: dict[str, Any],
        latency_ms: float,
        success_score: float,
        route_confidence: float | None = None,
    ) -> None:
        """Persist a workflow outcome and refresh the reusable cache entry."""

        now = time.time()
        normalized_goal = self._normalize_goal(goal)
        key = self._cache_key(workflow, goal)
        answer = str(result.get("answer") or "")
        metadata = dict(result.get("metadata") or {})
        metadata["learning_recorded_at"] = now
        if route_confidence is not None:
            metadata["route_confidence"] = route_confidence
        steps = list(result.get("steps") or [])
        sources = list(result.get("sources") or [])
        with self._lock, sqlite3.connect(self._path) as db:
            db.execute(
                """
                INSERT INTO workflow_runs (
                    workflow, goal, normalized_goal, latency_ms, success_score,
                    route_confidence, answer_chars, sources_count, steps_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow,
                    goal,
                    normalized_goal,
                    float(latency_ms),
                    float(success_score),
                    route_confidence,
                    len(answer),
                    len(sources),
                    len(steps),
                    now,
                ),
            )
            if success_score >= 0.72 and answer:
                db.execute(
                    """
                    INSERT INTO workflow_cache (
                        cache_key, workflow, goal, normalized_goal, answer, steps_json,
                        sources_json, metadata_json, success_score, created_at,
                        last_hit_at, hit_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        answer = excluded.answer,
                        steps_json = excluded.steps_json,
                        sources_json = excluded.sources_json,
                        metadata_json = excluded.metadata_json,
                        success_score = excluded.success_score,
                        created_at = excluded.created_at
                    """,
                    (
                        key,
                        workflow,
                        goal,
                        normalized_goal,
                        answer,
                        json.dumps(steps, default=str),
                        json.dumps(sources, default=str),
                        json.dumps(metadata, default=str),
                        float(success_score),
                        now,
                    ),
                )

    def summary(self, limit: int = 8) -> dict[str, Any]:
        """Return compact operational analytics for API and UI surfaces."""

        with self._lock, sqlite3.connect(self._path) as db:
            totals = db.execute(
                """
                SELECT workflow, COUNT(*), AVG(latency_ms), AVG(success_score),
                       AVG(COALESCE(route_confidence, 0.0))
                FROM workflow_runs
                GROUP BY workflow
                ORDER BY COUNT(*) DESC
                """
            ).fetchall()
            cache = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0), COALESCE(AVG(success_score), 0) FROM workflow_cache"
            ).fetchone()
            templates = db.execute(
                """
                SELECT workflow, goal, COUNT(*) AS uses, AVG(success_score) AS score, AVG(latency_ms) AS latency
                FROM workflow_runs
                GROUP BY workflow, normalized_goal
                HAVING uses >= 1
                ORDER BY uses DESC, score DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {
            "workflows": [
                {
                    "workflow": row[0],
                    "runs": int(row[1]),
                    "avg_latency_ms": round(float(row[2] or 0.0), 2),
                    "avg_success_score": round(float(row[3] or 0.0), 3),
                    "avg_route_confidence": round(float(row[4] or 0.0), 3),
                }
                for row in totals
            ],
            "cache": {
                "entries": int(cache[0] or 0),
                "hits": int(cache[1] or 0),
                "avg_success_score": round(float(cache[2] or 0.0), 3),
            },
            "templates": [
                {
                    "workflow": row[0],
                    "goal": row[1],
                    "uses": int(row[2]),
                    "success_score": round(float(row[3] or 0.0), 3),
                    "avg_latency_ms": round(float(row[4] or 0.0), 2),
                }
                for row in templates
            ],
        }

    def _init_db(self) -> None:
        with sqlite3.connect(self._path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    normalized_goal TEXT NOT NULL,
                    latency_ms REAL NOT NULL,
                    success_score REAL NOT NULL,
                    route_confidence REAL,
                    answer_chars INTEGER NOT NULL,
                    sources_count INTEGER NOT NULL,
                    steps_count INTEGER NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_cache (
                    cache_key TEXT PRIMARY KEY,
                    workflow TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    normalized_goal TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    success_score REAL NOT NULL,
                    created_at REAL NOT NULL,
                    last_hit_at REAL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_created ON workflow_runs(created_at)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON workflow_runs(workflow)")

    def _cache_key(self, workflow: str, goal: str) -> str:
        value = f"{workflow}:{self._normalize_goal(goal)}"
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _normalize_goal(self, goal: str) -> str:
        return " ".join(goal.lower().split())[:512]
