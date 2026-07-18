from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolAccess, ToolResult


class ProjectAnalyzer(Tool):
    name = "analyze_project"
    description = "Inspect the current repository for files, manifests, and source counts."
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
    _source_extensions = {
        ".c": "C",
        ".cpp": "C++",
        ".css": "CSS",
        ".go": "Go",
        ".html": "HTML",
        ".java": "Java",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".kt": "Kotlin",
        ".kts": "Kotlin",
        ".py": "Python",
        ".rs": "Rust",
        ".scss": "SCSS",
        ".swift": "Swift",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
    }

    def run(self, args: dict[str, Any], state) -> ToolResult:
        try:
            root = resolve_within_root(state_workspace_root(state), str(args.get("path", ".")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Project path not found or not allowed: {exc}")
        manifests = [
            name
            for name in (
                "pyproject.toml",
                "requirements.txt",
                "package.json",
                "README.md",
                "build.gradle",
                "build.gradle.kts",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
            )
            if (root / name).exists()
        ]
        source_counts: Counter[str] = Counter()
        preview: list[str] = []
        total_files = 0
        scan_errors: list[str] = []

        def record_error(error: OSError) -> None:
            if len(scan_errors) < 5:
                scan_errors.append(str(error))

        for current, directories, filenames in os.walk(root, onerror=record_error, followlinks=False):
            directories[:] = sorted(
                name
                for name in directories
                if name not in self._excluded_directories
                and not name.startswith(".tox")
                and not name.endswith(".egg-info")
            )
            current_path = Path(current)
            for filename in sorted(filenames):
                total_files += 1
                language = self._source_extensions.get(Path(filename).suffix.lower())
                if language is None:
                    continue
                source_counts[language] += 1
                if len(preview) < 12:
                    preview.append(str((current_path / filename).relative_to(root)))

        python_files = source_counts.get("Python", 0)
        languages = dict(sorted(source_counts.items(), key=lambda item: (-item[1], item[0])))
        summary = [
            f"root={root.resolve()}",
            f"manifests={', '.join(manifests) if manifests else 'none'}",
            f"source_files={sum(source_counts.values())}",
            f"languages={', '.join(f'{name}:{count}' for name, count in languages.items()) or 'none'}",
            f"scan_errors={len(scan_errors)}",
        ]
        return ToolResult(
            True,
            "\n".join(summary + preview),
            {
                "root": str(root),
                "manifests": manifests,
                "total_files": total_files,
                "source_files": sum(source_counts.values()),
                "python_files": python_files,
                "languages": languages,
                "scan_errors": scan_errors,
                "excluded_directories": sorted(self._excluded_directories),
            },
        )
