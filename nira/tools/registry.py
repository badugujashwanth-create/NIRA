from __future__ import annotations

from typing import TYPE_CHECKING

from nira.security.tool_policy import ApprovalCallback, ToolPermissionPolicy
from nira.tools.base import Tool, ToolAccess, ToolResult

if TYPE_CHECKING:
    from nira.core.agent_runtime import AgentState


class ToolRegistry:
    def __init__(self, permission_policy: ToolPermissionPolicy | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.permission_policy = permission_policy or ToolPermissionPolicy()

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
        access = tool.access_for(args)
        authorized, reason = self.permission_policy.authorize(name, args, access)
        if not authorized:
            return ToolResult(
                False,
                f"Blocked '{name}': explicit {access.value} approval is required.",
                {
                    "tool": name,
                    "access": access.value,
                    "permission_required": True,
                    "reason": reason,
                },
            )
        try:
            return tool.run(args, state)
        except Exception as exc:
            return ToolResult(False, f"Tool '{name}' failed: {exc}", {"tool": name})

    def set_approval_callback(self, callback: ApprovalCallback | None) -> None:
        self.permission_policy.approval_callback = callback

    def grant(self, *access_levels: ToolAccess) -> None:
        self.permission_policy.grant(*access_levels)
