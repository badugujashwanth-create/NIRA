from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkingMemoryItem:
    """A bounded in-RAM memory item for the current session."""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    importance: float = 0.5


class WorkingMemory:
    """Session-only LRU memory with TTL pruning."""

    def __init__(self, max_items: int = 128, ttl_sec: int = 3_600) -> None:
        self._max_items = max_items
        self._ttl_sec = ttl_sec
        self._items: OrderedDict[str, WorkingMemoryItem] = OrderedDict()

    def set(self, key: str, value: Any, importance: float = 0.5, ttl_sec: int | None = None) -> None:
        """Store a session item and prune expired or excess entries."""

        expires_at = time.time() + (self._ttl_sec if ttl_sec is None else ttl_sec)
        self._items[key] = WorkingMemoryItem(key=key, value=value, expires_at=expires_at, importance=importance)
        self._items.move_to_end(key)
        self.prune()

    def get(self, key: str) -> Any | None:
        """Return a stored item value if it has not expired."""

        self.prune()
        item = self._items.get(key)
        if not item:
            return None
        self._items.move_to_end(key)
        return item.value

    def values(self) -> list[Any]:
        """Return current session values in recency order."""

        self.prune()
        return [item.value for item in self._items.values()]

    def prune(self) -> None:
        """Remove expired items and shrink to max_items."""

        now = time.time()
        expired = [key for key, item in self._items.items() if item.expires_at and item.expires_at <= now]
        for key in expired:
            self._items.pop(key, None)
        while len(self._items) > self._max_items:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        self.prune()
        return len(self._items)
