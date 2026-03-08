from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionLevel:
    name: str
    rank: int


READ_ONLY = PermissionLevel("read_only", 1)
STANDARD = PermissionLevel("standard", 2)
DESTRUCTIVE = PermissionLevel("destructive", 3)
ADMIN = PermissionLevel("admin", 4)


class PermissionManager:
    LEVELS = {
        "read_only": READ_ONLY,
        "standard": STANDARD,
        "destructive": DESTRUCTIVE,
        "admin": ADMIN,
    }

    def __init__(self, current_level: str = "standard") -> None:
        self._lock = threading.Lock()
        self.current = self.LEVELS.get(current_level, STANDARD)

    def require(self, required: PermissionLevel) -> bool:
        with self._lock:
            return self.current.rank >= required.rank

    def set_level(self, level_name: str) -> None:
        with self._lock:
            self.current = self.LEVELS.get(level_name, self.current)

    def force_safe_mode(self) -> None:
        with self._lock:
            self.current = READ_ONLY

