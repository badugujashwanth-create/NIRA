from __future__ import annotations

import shlex
from pathlib import Path

from nira_core.sandbox import PermissionPolicy, SubprocessSandbox, ToolRequest
from nira_core.tools.base import ToolResult


class ShellTool:
    """Allowlisted subprocess tool; it never invokes a user-controlled shell."""

    name = "shell"

    def __init__(self, permissions: PermissionPolicy, sandbox: SubprocessSandbox, workspace_root: Path) -> None:
        self._permissions = permissions
        self._sandbox = sandbox
        self._workspace_root = workspace_root.resolve()

    async def run(self, payload: dict[str, object]) -> ToolResult:
        raw_command = payload.get("command", ())
        if isinstance(raw_command, str):
            command = tuple(shlex.split(raw_command))
        else:
            command = tuple(str(part) for part in raw_command)
        if not command:
            return ToolResult(False, error="missing_command")
        cwd = Path(str(payload.get("cwd", self._workspace_root)))
        if not cwd.is_absolute():
            cwd = self._workspace_root / cwd
        decision = self._permissions.decide(ToolRequest(tool_name=self.name, action="execute", path=cwd, command=command))
        if not decision.allowed:
            return ToolResult(False, error=decision.reason)
        try:
            result = await self._sandbox.run(command, cwd=cwd)
            return ToolResult(result.ok, output=result.stdout, error=result.stderr, data={"returncode": result.returncode})
        except Exception as exc:
            return ToolResult(False, error=str(exc))
