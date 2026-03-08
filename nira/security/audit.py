from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nira_agent.security.encryption import EncryptionManager
from nira_agent.storage.sql_store import SQLStore


class SecureAuditLogger:
    def __init__(
        self,
        encryption: EncryptionManager,
        path: Path | None = None,
        sql_store: SQLStore | None = None,
    ) -> None:
        self.encryption = encryption
        self.path = path or (Path.home() / ".nira_agent" / "logs" / "audit.log.enc")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sql_store = sql_store
        self._lock = threading.Lock()

    def log(self, event: str, payload: dict[str, Any]) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        raw = json.dumps(row, ensure_ascii=True)
        encrypted = self.encryption.encrypt_text(raw)
        if self.sql_store and self.sql_store.available:
            self.sql_store.insert_audit(row["ts"], event, encrypted)
            return
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(encrypted + "\n")

    def read_decrypted(self) -> list[dict[str, Any]]:
        if self.sql_store and self.sql_store.available:
            rows: list[dict[str, Any]] = []
            for _, _, enc_payload in self.sql_store.latest_audit():
                try:
                    plain = self.encryption.decrypt_text(enc_payload)
                    rows.append(json.loads(plain))
                except Exception:
                    continue
            return rows

        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        plain = self.encryption.decrypt_text(line)
                        rows.append(json.loads(plain))
                    except Exception:
                        continue
        return rows
