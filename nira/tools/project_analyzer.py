from __future__ import annotations

from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolResult


class ProjectAnalyzer(Tool):
    name = "analyze_project"
    description = "Inspect the current repository for files, manifests, and source counts."

    def run(self, args: dict[str, Any], state) -> ToolResult:
        try:
            root = resolve_within_root(state_workspace_root(state), str(args.get("path", ".")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Project path not found or not allowed: {exc}")
        manifests = [name for name in ("pyproject.toml", "requirements.txt", "package.json", "README.md") if (root / name).exists()]
        try:
            code_files = list(root.rglob("*.py"))
        except OSError as exc:
            return ToolResult(False, f"Project scan failed: {exc}")
        summary = [
            f"root={root.resolve()}",
            f"manifests={', '.join(manifests) if manifests else 'none'}",
            f"python_files={len(code_files)}",
        ]
        preview = [str(path.relative_to(root)) for path in code_files[:10]]
        return ToolResult(True, "\n".join(summary + preview), {"root": str(root), "manifests": manifests, "python_files": len(code_files)})
