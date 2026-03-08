from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from nira_agent.storage.sql_store import SQLStore


class UserPreferences:
    def __init__(self, path: Path | None = None, sql_store: SQLStore | None = None) -> None:
        self.path = path or (Path.home() / ".nira_agent" / "memory" / "preferences.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.sql_store = sql_store
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.sql_store and self.sql_store.available:
            return {}
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        if self.sql_store and self.sql_store.available:
            return self.sql_store.get_preference(key, default)
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        if self.sql_store and self.sql_store.available:
            self.sql_store.set_preference(key, value)
            return
        with self._lock:
            self._data[key] = value
            self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
