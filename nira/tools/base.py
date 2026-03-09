from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nira.core.agent_runtime import AgentState


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "output": self.output, "data": dict(self.data)}


class Tool(ABC):
    name: str = ""
    description: str = ""

    @abstractmethod
    def run(self, args: dict[str, Any], state: "AgentState") -> ToolResult:
        raise NotImplementedError
