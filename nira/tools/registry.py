from __future__ import annotations

from typing import TYPE_CHECKING

from nira.tools.base import Tool, ToolResult

if TYPE_CHECKING:
    from nira.core.agent_runtime import AgentState


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(self._tools.keys())

    def execute(self, name: str, args: dict, state: "AgentState") -> ToolResult:
        tool = self.get(name)
        if tool is None:
            return ToolResult(False, f"Tool '{name}' is not registered.")
        try:
            return tool.run(args, state)
        except Exception as exc:
            return ToolResult(False, f"Tool '{name}' failed: {exc}", {"tool": name})
