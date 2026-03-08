from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)


UndoFn = Callable[[], ToolResult]


@dataclass
class ExecutedAction:
    description: str
    undoable: bool
    undo_fn: UndoFn | None = None

