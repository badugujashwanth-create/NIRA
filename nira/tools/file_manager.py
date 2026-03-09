from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolResult


class FileManager(Tool):
    name = "file_manager"
    description = "Read, write, list, or create local files and directories."

    def run(self, args: dict[str, Any], state) -> ToolResult:
        action = str(args.get("action", "read")).lower()
        try:
            root = state_workspace_root(state)
            path = resolve_within_root(root, str(args.get("path", ".")))
        except (PathSecurityError, OSError, RuntimeError) as exc:
            return ToolResult(False, f"Invalid file path: {exc}")
        if action == "read":
            try:
                if not path.exists():
                    return ToolResult(False, f"Path not found: {path}")
                if path.is_dir():
                    entries = sorted(item.name for item in path.iterdir())
                    return ToolResult(True, "\n".join(entries[:200]), {"count": len(entries), "path": str(path)})
                return ToolResult(True, path.read_text(encoding="utf-8", errors="ignore"), {"path": str(path)})
            except OSError as exc:
                return ToolResult(False, f"Read failed for {path}: {exc}")
        if action == "write":
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(args.get("content", "")), encoding="utf-8")
                return ToolResult(True, f"Wrote file {path}", {"path": str(path)})
            except OSError as exc:
                return ToolResult(False, f"Write failed for {path}: {exc}")
        if action == "append":
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(str(args.get("content", "")))
                return ToolResult(True, f"Appended file {path}", {"path": str(path)})
            except OSError as exc:
                return ToolResult(False, f"Append failed for {path}: {exc}")
        if action == "mkdir":
            try:
                path.mkdir(parents=True, exist_ok=True)
                return ToolResult(True, f"Created directory {path}", {"path": str(path)})
            except OSError as exc:
                return ToolResult(False, f"Directory creation failed for {path}: {exc}")
        return ToolResult(False, f"Unsupported file_manager action: {action}")


class UpdateConfigTool(Tool):
    name = "update_config"
    description = "Update a local JSON, env, or plain-text config file."

    def run(self, args: dict[str, Any], state) -> ToolResult:
        try:
            root = state_workspace_root(state)
            target = resolve_within_root(root, str(args.get("path", ".env")))
        except (PathSecurityError, OSError, RuntimeError) as exc:
            return ToolResult(False, f"Invalid config path: {exc}")
        setting = str(args.get("setting", "")).strip()
        value = args.get("value", "")
        content = str(args.get("content", "")).strip()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(False, f"Could not prepare config directory: {exc}")
        if target.suffix.lower() == ".json":
            payload: dict[str, Any] = {}
            backup_path = ""
            if target.exists():
                try:
                    payload = json.loads(target.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    backup = target.with_suffix(f"{target.suffix}.invalid.bak")
                    try:
                        backup.write_text(target.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
                    except OSError as exc:
                        return ToolResult(False, f"Config JSON is invalid and backup failed: {exc}")
                    payload = {}
                    backup_path = str(backup)
            if setting:
                payload[setting] = value
            elif content:
                payload["content"] = content
            try:
                target.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
                return ToolResult(
                    True,
                    f"Updated JSON config {target}",
                    {"path": str(target), "backup_path": backup_path},
                )
            except OSError as exc:
                return ToolResult(False, f"Could not write JSON config {target}: {exc}")

        lines = []
        if target.exists():
            try:
                lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError as exc:
                return ToolResult(False, f"Could not read config {target}: {exc}")
        if setting:
            updated = False
            prefix = f"{setting}="
            rendered_value = self._render_config_value(value)
            for index, line in enumerate(lines):
                if line.startswith(prefix):
                    lines[index] = f"{setting}={rendered_value}"
                    updated = True
                    break
            if not updated:
                lines.append(f"{setting}={rendered_value}")
        if content:
            lines.append(content)
        if not lines:
            return ToolResult(True, "No config changes requested.", {"path": str(target)})
        try:
            target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Could not write config {target}: {exc}")
        return ToolResult(True, f"Updated config {target}", {"path": str(target)})

    @staticmethod
    def _render_config_value(value: Any) -> str:
        body = str(value)
        if any(char in body for char in "\r\n") or any(char in body for char in ('"', "#", " ")):
            return json.dumps(body, ensure_ascii=True)
        return body
