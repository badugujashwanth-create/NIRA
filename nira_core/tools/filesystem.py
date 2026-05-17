from __future__ import annotations

from pathlib import Path

from nira_core.sandbox import PermissionPolicy, ToolRequest
from nira_core.tools.base import ToolResult


class FilesystemTool:
    """Workspace-scoped filesystem reader and writer."""

    name = "filesystem"

    def __init__(self, permissions: PermissionPolicy, workspace_root: Path) -> None:
        self._permissions = permissions
        self._workspace_root = workspace_root.resolve()

    async def run(self, payload: dict[str, object]) -> ToolResult:
        action = str(payload.get("action", "read"))
        raw_path = Path(str(payload.get("path", ".")))
        path = raw_path if raw_path.is_absolute() else self._workspace_root / raw_path
        decision = self._permissions.decide(ToolRequest(tool_name=self.name, action=action, path=path))
        if not decision.allowed:
            return ToolResult(False, error=decision.reason)
        try:
            if action == "read":
                return ToolResult(True, output=path.read_text(encoding="utf-8"))
            if action == "write":
                content = str(payload.get("content", ""))
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                return ToolResult(True, output=str(path))
            if action == "list":
                items = [item.name for item in path.iterdir()]
                return ToolResult(True, data={"items": items}, output="\n".join(items))
            return ToolResult(False, error=f"unsupported_filesystem_action:{action}")
        except Exception as exc:
            return ToolResult(False, error=str(exc))
