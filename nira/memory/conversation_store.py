from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Conversation:
    conversation_id: str
    title: str
    created_at: str
    updated_at: str
    pinned: bool
    message_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "conversation_id": self.conversation_id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "pinned": self.pinned,
            "message_count": self.message_count,
        }


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content, "created_at": self.created_at}


class ConversationStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def latest_or_create(self) -> Conversation:
        with closing(sqlite3.connect(self.database_path)) as conn:
            row = conn.execute(
                "SELECT conversation_id FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return self.create()
        conversation = self.get(str(row[0]))
        return conversation if conversation is not None else self.create()

    def create(self, title: str = "New conversation") -> Conversation:
        conversation_id = uuid.uuid4().hex[:12]
        now = _utc_now()
        clean_title = self._clean_title(title)
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.execute(
                "INSERT INTO conversations(conversation_id, title, created_at, updated_at, pinned) VALUES (?, ?, ?, ?, 0)",
                (conversation_id, clean_title, now, now),
            )
            conn.commit()
        return Conversation(conversation_id, clean_title, now, now, False, 0)

    def get(self, conversation_id: str) -> Conversation | None:
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at, c.pinned, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN conversation_messages m ON m.conversation_id = c.conversation_id
                WHERE c.conversation_id = ?
                GROUP BY c.conversation_id
                """,
                (conversation_id,),
            ).fetchone()
        return self._conversation_from_row(row) if row else None

    def list(self, limit: int = 50) -> list[Conversation]:
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at, c.pinned, COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN conversation_messages m ON m.conversation_id = c.conversation_id
                GROUP BY c.conversation_id
                ORDER BY c.pinned DESC, c.updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._conversation_from_row(row) for row in rows]

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        body = content.strip()
        if not body:
            return
        now = _utc_now()
        with closing(sqlite3.connect(self.database_path)) as conn:
            existing = conn.execute(
                "SELECT title FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if existing is None:
                raise KeyError(f"Unknown conversation: {conversation_id}")
            conn.execute(
                "INSERT INTO conversation_messages(conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, body, now),
            )
            title = str(existing[0])
            if role == "user" and title == "New conversation":
                title = self._clean_title(body)
            conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                (title, now, conversation_id),
            )
            conn.commit()

    def messages(self, conversation_id: str, limit: int = 200) -> list[ConversationMessage]:
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, max(1, min(limit, 2000))),
            ).fetchall()
        return [
            ConversationMessage(str(row["role"]), str(row["content"]), str(row["created_at"]))
            for row in reversed(rows)
        ]

    def search(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        term = query.strip()
        if not term:
            return []
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT c.conversation_id, c.title, m.role, m.content, m.created_at
                FROM conversation_messages m
                JOIN conversations c ON c.conversation_id = m.conversation_id
                WHERE m.content LIKE ? ESCAPE '\\' OR c.title LIKE ? ESCAPE '\\'
                ORDER BY m.id DESC
                LIMIT ?
                """,
                (pattern, pattern, max(1, min(limit, 100))),
            ).fetchall()
        return [
            {
                "conversation_id": str(row["conversation_id"]),
                "title": str(row["title"]),
                "role": str(row["role"]),
                "content": str(row["content"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def set_pinned(self, conversation_id: str, pinned: bool) -> bool:
        with closing(sqlite3.connect(self.database_path)) as conn:
            cursor = conn.execute(
                "UPDATE conversations SET pinned = ?, updated_at = ? WHERE conversation_id = ?",
                (int(pinned), _utc_now(), conversation_id),
            )
            conn.commit()
        return cursor.rowcount == 1

    def rename(self, conversation_id: str, title: str) -> bool:
        with closing(sqlite3.connect(self.database_path)) as conn:
            cursor = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE conversation_id = ?",
                (self._clean_title(title), _utc_now(), conversation_id),
            )
            conn.commit()
        return cursor.rowcount == 1

    def delete(self, conversation_id: str) -> bool:
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.execute("DELETE FROM conversation_messages WHERE conversation_id = ?", (conversation_id,))
            cursor = conn.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            conn.commit()
        return cursor.rowcount == 1

    def export_markdown(self, conversation_id: str, output_path: Path) -> Path:
        conversation = self.get(conversation_id)
        if conversation is None:
            raise KeyError(f"Unknown conversation: {conversation_id}")
        output = Path(output_path).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {conversation.title}", "", f"Conversation: `{conversation.conversation_id}`", ""]
        for message in self.messages(conversation_id):
            lines.extend([f"## {message.role.title()}", "", message.content, ""])
        output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return output

    def _ensure_schema(self) -> None:
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    pinned INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(conversation_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_messages_conversation ON conversation_messages(conversation_id, id)"
            )
            conn.commit()

    @staticmethod
    def _clean_title(title: str) -> str:
        clean = " ".join(title.split()).strip()
        return (clean[:72] or "New conversation").rstrip()

    @staticmethod
    def _conversation_from_row(row: sqlite3.Row) -> Conversation:
        return Conversation(
            conversation_id=str(row["conversation_id"]),
            title=str(row["title"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            pinned=bool(row["pinned"]),
            message_count=int(row["message_count"]),
        )
