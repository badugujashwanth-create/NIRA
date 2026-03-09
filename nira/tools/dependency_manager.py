from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nira.tools.base import Tool, ToolResult


class DependencyManager(Tool):
    name = "add_dependency"
    description = "Add a dependency to a local requirements or package manifest."

    def run(self, args: dict[str, Any], state) -> ToolResult:
        dependency = str(args.get("name") or args.get("dependency") or "").strip()
        version = str(args.get("version", "")).strip()
        if not dependency:
            return ToolResult(True, "No dependency specified; nothing changed.", {})
        target = self._detect_manifest(Path.cwd())
        if target.suffix == ".txt":
            entry = dependency if not version else f"{dependency}=={version}"
            existing = target.read_text(encoding="utf-8", errors="ignore").splitlines() if target.exists() else []
            updated = False
            normalized_name = self._normalize_name(dependency)
            for index, line in enumerate(existing):
                if self._normalize_name(line.split("==", 1)[0].strip()) == normalized_name:
                    existing[index] = entry
                    updated = True
                    break
            if not updated:
                existing.append(entry)
            try:
                target.write_text("\n".join(line for line in existing if line).strip() + "\n", encoding="utf-8")
            except OSError as exc:
                return ToolResult(False, f"Could not update {target.name}: {exc}", {"path": str(target)})
            return ToolResult(True, f"Recorded dependency in {target.name}: {entry}", {"path": str(target)})
        if target.suffix == ".json":
            try:
                payload = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            except json.JSONDecodeError as exc:
                return ToolResult(False, f"package.json is invalid JSON: {exc}", {"path": str(target)})
            dependencies = payload.setdefault("dependencies", {})
            dependencies[dependency] = version or "latest"
            try:
                target.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
            except OSError as exc:
                return ToolResult(False, f"Could not update {target.name}: {exc}", {"path": str(target)})
            return ToolResult(True, f"Recorded dependency in {target.name}: {dependency}", {"path": str(target)})
        if target.suffix == ".toml":
            try:
                updated = self._update_pyproject(target, dependency, version)
            except OSError as exc:
                return ToolResult(False, f"Could not update {target.name}: {exc}", {"path": str(target)})
            if not updated:
                return ToolResult(False, f"Unsupported pyproject.toml layout in {target.name}", {"path": str(target)})
            return ToolResult(True, f"Recorded dependency in {target.name}: {dependency}", {"path": str(target)})
        entry = dependency if not version else f"{dependency}=={version}"
        try:
            target.write_text(entry + "\n", encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Could not update {target.name}: {exc}", {"path": str(target)})
        return ToolResult(True, f"Recorded dependency in {target.name}: {entry}", {"path": str(target)})

    @staticmethod
    def _detect_manifest(root: Path) -> Path:
        for candidate in (root / "requirements.txt", root / "package.json", root / "pyproject.toml"):
            if candidate.exists():
                return candidate
        return root / "requirements.txt"

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name.strip().lower())

    def _update_pyproject(self, path: Path, dependency: str, version: str) -> bool:
        entry = dependency if not version else f"{dependency}=={version}"
        text = path.read_text(encoding="utf-8")
        dependency_literal = f'"{entry}"'

        project_block = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", text)
        if project_block:
            block = project_block.group(1)
            deps_match = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", block)
            if deps_match:
                current_entries = re.findall(r'"([^"]+)"', deps_match.group(1))
                normalized = {self._normalize_name(item.split("==", 1)[0]) for item in current_entries}
                if self._normalize_name(dependency) not in normalized:
                    replacement = deps_match.group(0).rstrip("]") + f',\n  {dependency_literal}\n]'
                    new_block = block.replace(deps_match.group(0), replacement, 1)
                    path.write_text(text.replace(block, new_block, 1), encoding="utf-8")
                return True
            insertion = f'dependencies = [\n  {dependency_literal}\n]\n'
            new_block = f"{insertion}{block}"
            path.write_text(text.replace(block, new_block, 1), encoding="utf-8")
            return True

        poetry_block = re.search(r"(?ms)^\[tool\.poetry\.dependencies\]\s*(.*?)(?=^\[|\Z)", text)
        if poetry_block:
            block = poetry_block.group(1)
            lines = [line.rstrip() for line in block.splitlines()]
            normalized = {self._normalize_name(line.split("=", 1)[0].strip()) for line in lines if "=" in line}
            if self._normalize_name(dependency) not in normalized:
                version_value = version or "*"
                lines.append(f'{dependency} = "{version_value}"')
                new_block = "\n".join(line for line in lines if line).strip() + "\n"
                path.write_text(text.replace(block, new_block, 1), encoding="utf-8")
            return True

        return False
