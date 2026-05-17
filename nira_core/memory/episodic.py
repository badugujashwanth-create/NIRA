from __future__ import annotations

import json
import math
import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from nira_core.config import MemoryPolicyConfig


@dataclass(frozen=True, slots=True)
class Episode:
    """A durable task or interaction memory."""

    id: int
    kind: str
    content: str
    importance: float
    created_at: float
    expires_at: float | None
    metadata: str = "{}"
    pinned: bool = False
    archived_at: float | None = None


class EpisodicMemory:
    """SQLite-backed history with TTL, decay, and archival compression hooks."""

    def __init__(self, path: Path, policy: MemoryPolicyConfig) -> None:
        self._path = path
        self._policy = policy
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def append(self, kind: str, content: str, importance: float = 0.5, metadata: str = "{}") -> int:
        """Append a bounded episode and return its row id."""

        now = time.time()
        content_hash = _content_hash(content)
        expires_at = now + self._policy.episodic_ttl_days * 86_400
        with self._connect() as conn:
            duplicate = conn.execute(
                "SELECT id, importance FROM episodes WHERE content_hash = ? AND archived_at IS NULL LIMIT 1",
                (content_hash,),
            ).fetchone()
            if duplicate is not None:
                conn.execute(
                    "UPDATE episodes SET importance = MAX(importance, ?), created_at = ? WHERE id = ?",
                    (importance, now, duplicate["id"]),
                )
                conn.commit()
                return int(duplicate["id"])
            cur = conn.execute(
                """
                INSERT INTO episodes(kind, content, importance, created_at, expires_at, metadata, pinned, archived_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
                """,
                (kind, content, importance, now, expires_at, metadata, content_hash),
            )
            conn.commit()
            return int(cur.lastrowid)

    def search(self, query: str, limit: int = 8) -> list[Episode]:
        """Search recent episodes using lightweight SQLite matching."""

        like = f"%{query}%"
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, kind, content, importance, created_at, expires_at, metadata, pinned, archived_at
                FROM episodes
                WHERE archived_at IS NULL AND (expires_at IS NULL OR expires_at > ?) AND content LIKE ?
                ORDER BY pinned DESC, importance DESC, created_at DESC
                LIMIT ?
                """,
                (now, like, limit),
            ).fetchall()
        return [self._episode_from_row(row) for row in rows]

    def recent(self, limit: int = 20, include_archived: bool = False) -> list[Episode]:
        """Return recent non-expired episodes."""

        now = time.time()
        archive_clause = "" if include_archived else "AND archived_at IS NULL"
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, kind, content, importance, created_at, expires_at, metadata, pinned, archived_at
                FROM episodes
                WHERE (expires_at IS NULL OR expires_at > ?) {archive_clause}
                ORDER BY pinned DESC, created_at DESC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [self._episode_from_row(row) for row in rows]

    def timeline(self, limit: int = 50, include_archived: bool = False) -> list[Episode]:
        """Return a memory timeline ordered for inspection."""

        return self.recent(limit=limit, include_archived=include_archived)

    def delete(self, episode_id: int) -> bool:
        """Delete one episode by id."""

        with self._connect() as conn:
            cur = conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            conn.commit()
            return cur.rowcount > 0

    def pin(self, episode_id: int, pinned: bool = True) -> bool:
        """Pin or unpin a memory so it remains prominent."""

        with self._connect() as conn:
            cur = conn.execute("UPDATE episodes SET pinned = ? WHERE id = ?", (1 if pinned else 0, episode_id))
            conn.commit()
            return cur.rowcount > 0

    def archive(self, episode_id: int) -> bool:
        """Archive one episode without deleting it."""

        with self._connect() as conn:
            cur = conn.execute("UPDATE episodes SET archived_at = ? WHERE id = ?", (time.time(), episode_id))
            conn.commit()
            return cur.rowcount > 0

    def summaries(self, limit: int = 20) -> list[dict[str, object]]:
        """Return compact memory summaries for UI inspection."""

        return [
            {
                "id": episode.id,
                "kind": episode.kind,
                "summary": self._archive_summary(episode.content),
                "importance": episode.importance,
                "created_at": episode.created_at,
                "pinned": episode.pinned,
                "metadata": _metadata_json(episode.metadata),
            }
            for episode in self.timeline(limit=limit)
        ]

    def health(self) -> dict[str, object]:
        """Return memory growth and fragmentation indicators."""

        with self._connect() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0])
            active = int(conn.execute("SELECT COUNT(*) FROM episodes WHERE archived_at IS NULL").fetchone()[0])
            archived = total - active
            pinned = int(conn.execute("SELECT COUNT(*) FROM episodes WHERE pinned = 1").fetchone()[0])
            duplicate_hashes = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM (
                      SELECT content_hash FROM episodes
                      WHERE content_hash IS NOT NULL
                      GROUP BY content_hash
                      HAVING COUNT(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
        fragmentation = archived / max(1, total)
        return {
            "total": total,
            "active": active,
            "archived": archived,
            "pinned": pinned,
            "duplicate_hashes": duplicate_hashes,
            "fragmentation": fragmentation,
        }

    def decay_and_prune(self) -> dict[str, int]:
        """Apply exponential decay, archive old important entries, and delete expired entries."""

        now = time.time()
        half_life_sec = max(1.0, self._policy.decay_half_life_days * 86_400)
        archived = 0
        deleted = 0
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, content, importance, created_at, metadata, pinned FROM episodes WHERE archived_at IS NULL"
            ).fetchall()
            for row_id, kind, content, importance, created_at, metadata, pinned in rows:
                if bool(pinned):
                    continue
                age = max(0.0, now - float(created_at))
                decayed = float(importance) * math.pow(0.5, age / half_life_sec)
                if age >= self._policy.archive_after_days * 86_400 and decayed >= self._policy.min_importance:
                    summary = self._archive_summary(content)
                    conn.execute(
                        """
                        INSERT INTO episode_archive(original_id, kind, summary, importance, archived_at, metadata)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (row_id, kind, summary, decayed, now, metadata),
                    )
                    cur = conn.execute("UPDATE episodes SET archived_at = ? WHERE id = ?", (now, row_id))
                    archived += max(0, cur.rowcount)
                elif decayed < self._policy.min_importance:
                    cur = conn.execute("DELETE FROM episodes WHERE id = ?", (row_id,))
                    deleted += max(0, cur.rowcount)
                else:
                    conn.execute("UPDATE episodes SET importance = ? WHERE id = ?", (decayed, row_id))
            expired = conn.execute("DELETE FROM episodes WHERE pinned = 0 AND expires_at IS NOT NULL AND expires_at <= ?", (now,))
            deleted += max(0, expired.rowcount)
            conn.commit()
        return {"archived": archived, "deleted": deleted}

    def _archive_summary(self, content: str) -> str:
        words = content.split()
        return " ".join(words[:80])

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    archived_at REAL,
                    content_hash TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS episode_archive (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_id INTEGER NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    importance REAL NOT NULL,
                    archived_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_importance ON episodes(importance)")
            self._ensure_column(conn, "episodes", "pinned", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "episodes", "archived_at", "REAL")
            self._ensure_column(conn, "episodes", "content_hash", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_hash ON episodes(content_hash)")
            conn.commit()

    def _episode_from_row(self, row: sqlite3.Row) -> Episode:
        return Episode(
            id=int(row["id"]),
            kind=str(row["kind"]),
            content=str(row["content"]),
            importance=float(row["importance"]),
            created_at=float(row["created_at"]),
            expires_at=float(row["expires_at"]) if row["expires_at"] is not None else None,
            metadata=str(row["metadata"]),
            pinned=bool(row["pinned"]),
            archived_at=float(row["archived_at"]) if row["archived_at"] is not None else None,
        )

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _metadata_json(raw: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _content_hash(content: str) -> str:
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
