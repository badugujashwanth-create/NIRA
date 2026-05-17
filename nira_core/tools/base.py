from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Structured result returned by every tool."""

    ok: bool
    output: str = ""
    data: dict[str, object] = field(default_factory=dict)
    error: str = ""


class Tool(Protocol):
    """Async tool contract."""

    name: str

    async def run(self, payload: dict[str, object]) -> ToolResult:
        """Execute a tool action."""
