from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolAccess, ToolResult


class WorkspaceSearch(Tool):
    """Bounded, read-only text search inside the selected workspace."""

    name = "search_workspace"
    description = "Search text files inside the selected workspace with fixed file and result limits."
    access = ToolAccess.READ

    _excluded_directories = {
        ".git",
        ".nira",
        ".pytest_cache",
        ".pytest-tmp",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "playwright-report",
        "target",
        "test-results",
        "venv",
    }
    _text_extensions = {
        ".c",
        ".cpp",
        ".css",
        ".go",
        ".html",
        ".java",
        ".js",
        ".json",
        ".jsx",
        ".kt",
        ".kts",
        ".md",
        ".py",
        ".rs",
        ".scss",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".yaml",
        ".yml",
    }

    def run(self, args: dict[str, Any], state) -> ToolResult:
        query = str(args.get("query", "")).strip()
        if len(query) < 2:
            return ToolResult(False, "Search query must contain at least two characters.")
        try:
            root = resolve_within_root(
                state_workspace_root(state),
                str(args.get("path", ".")),
                must_exist=True,
            )
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Search path not found or not allowed: {exc}")
        if not root.is_dir():
            return ToolResult(False, f"Search path is not a directory: {root}")

        max_files = max(1, min(int(args.get("max_files", 500)), 1_000))
        max_matches = max(1, min(int(args.get("max_matches", 50)), 100))
        max_file_bytes = max(1_024, min(int(args.get("max_file_bytes", 512_000)), 1_048_576))
        needle = query.casefold()
        scanned_files = 0
        skipped_large = 0
        matches: list[dict[str, Any]] = []

        for current, directories, filenames in os.walk(root, followlinks=False):
            directories[:] = sorted(
                name
                for name in directories
                if name not in self._excluded_directories
                and not name.startswith(".tox")
                and not name.endswith(".egg-info")
            )
            current_path = Path(current)
            for filename in sorted(filenames):
                path = current_path / filename
                if path.suffix.lower() not in self._text_extensions:
                    continue
                if scanned_files >= max_files or len(matches) >= max_matches:
                    break
                try:
                    if path.stat().st_size > max_file_bytes:
                        skipped_large += 1
                        continue
                    body = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                scanned_files += 1
                for line_number, line in enumerate(body.splitlines(), start=1):
                    if needle not in line.casefold():
                        continue
                    matches.append(
                        {
                            "path": str(path.relative_to(root)),
                            "line": line_number,
                            "preview": line.strip()[:240],
                        }
                    )
                    if len(matches) >= max_matches:
                        break
            if scanned_files >= max_files or len(matches) >= max_matches:
                break

        output = "\n".join(
            f"{item['path']}:{item['line']}: {item['preview']}" for item in matches
        )
        if not output:
            output = f"No matches found for {query!r}."
        return ToolResult(
            True,
            output,
            {
                "query": query,
                "root": str(root),
                "matches": matches,
                "match_count": len(matches),
                "scanned_files": scanned_files,
                "skipped_large_files": skipped_large,
                "limits": {
                    "max_files": max_files,
                    "max_matches": max_matches,
                    "max_file_bytes": max_file_bytes,
                },
            },
        )
