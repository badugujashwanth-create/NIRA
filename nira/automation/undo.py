from __future__ import annotations

import threading
from collections import deque

from nira.automation.models import ExecutedAction, ToolResult


class UndoStack:
    def __init__(self, max_size: int = 200) -> None:
        self._items: deque[ExecutedAction] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def push(self, action: ExecutedAction) -> None:
        with self._lock:
            self._items.append(action)

    def undo_last(self) -> ToolResult:
        with self._lock:
            if not self._items:
                return ToolResult(False, "No actions available to undo.")
            action = self._items.pop()
        if not action.undoable or not action.undo_fn:
            return ToolResult(False, f"Action is not undoable: {action.description}")
        return action.undo_fn()
