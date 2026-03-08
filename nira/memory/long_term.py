from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nira_agent.security.encryption import EncryptionManager
from nira_agent.storage.sql_store import SQLStore


@dataclass
class MemoryRecord:
    ts: str
    kind: str
    content: str


class LongTermMemoryStore:
    def __init__(
        self,
        encryption: EncryptionManager,
        path: Path | None = None,
        sql_store: SQLStore | None = None,
    ) -> None:
        self.encryption = encryption
        self.path = path or (Path.home() / ".nira_agent" / "memory" / "long_term.mem.enc")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sql_store = sql_store
        self._lock = threading.Lock()

    def append(self, kind: str, content: str) -> None:
        record = MemoryRecord(
            ts=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            content=content,
        )
        payload = self.encryption.encrypt_text(record.content)
        if self.sql_store and self.sql_store.available:
            self.sql_store.insert_memory(record.ts, record.kind, payload)
            return

        payload_row = self.encryption.encrypt_text(json.dumps(record.__dict__, ensure_ascii=True))
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(payload_row + "\n")

    def latest(self, limit: int = 12) -> list[MemoryRecord]:
        if self.sql_store and self.sql_store.available:
            rows = []
            for ts, kind, enc_content in self.sql_store.latest_memory(limit):
                try:
                    content = self.encryption.decrypt_text(enc_content)
                    rows.append(MemoryRecord(ts=ts, kind=kind, content=content))
                except Exception:
                    continue
            return rows

        if not self.path.exists():
            return []
        rows: list[MemoryRecord] = []
        with self._lock:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                plain = self.encryption.decrypt_text(line.strip())
                payload = json.loads(plain)
                rows.append(MemoryRecord(**payload))
            except Exception:
                continue
        return rows
