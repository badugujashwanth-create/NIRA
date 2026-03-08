from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional, Tuple


UndoCallable = Callable[[], Tuple[bool, str]]


@dataclass
class UndoEntry:
    description: str
    undoable: bool
    undo: Optional[UndoCallable] = None


class UndoStack:
    def __init__(self, max_items: int = 100) -> None:
        self._items: Deque[UndoEntry] = deque(maxlen=max_items)

    def push(self, entry: UndoEntry) -> None:
        self._items.append(entry)

    def undo_last(self) -> tuple[bool, str]:
        if not self._items:
            return False, "No actions to undo."
        entry = self._items.pop()
        if not entry.undoable or not entry.undo:
            return False, f"Action not undoable: {entry.description}"
        return entry.undo()

    def can_undo(self) -> bool:
        return bool(self._items)

