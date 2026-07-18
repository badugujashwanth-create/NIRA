from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
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


class ToolAccess(str, Enum):
    READ = "read"
    STATE = "state"
    WORKSPACE_WRITE = "workspace_write"
    PROCESS = "process"
    NETWORK = "network"


class Tool(ABC):
    name: str = ""
    description: str = ""
    access: ToolAccess = ToolAccess.READ

    def access_for(self, args: dict[str, Any]) -> ToolAccess:
        return self.access

    @abstractmethod
    def run(self, args: dict[str, Any], state: "AgentState") -> ToolResult:
        raise NotImplementedError
