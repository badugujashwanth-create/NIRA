from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class PluginResult:
    plugin: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Plugin(Protocol):
    name: str

    def can_handle(self, query: str) -> bool:
        ...

    def execute(self, query: str) -> PluginResult:
        ...
