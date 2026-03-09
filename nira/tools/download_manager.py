from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import requests

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root, validate_public_http_url
from nira.tools.base import Tool, ToolResult


class DownloadManager(Tool):
    name = "download_resource"
    description = "Download or copy a local resource when explicitly requested."

    def __init__(self, web_enabled: bool = False) -> None:
        self.web_enabled = web_enabled

    def run(self, args: dict[str, Any], state) -> ToolResult:
        source = str(args.get("source", "")).strip()
        if not source:
            return ToolResult(True, "No download requested.", {})
        destination_name = str(args.get("destination") or Path(source).name or "downloaded_resource")
        try:
            root = Path(str(((getattr(state, "context", {}) or {}).get("artifacts_dir")) or state_workspace_root(state))).expanduser().resolve()
            destination = resolve_within_root(root, destination_name)
            destination.parent.mkdir(parents=True, exist_ok=True)
        except (PathSecurityError, OSError, RuntimeError) as exc:
            return ToolResult(False, f"Invalid download destination: {exc}")
        if source.startswith(("http://", "https://")):
            if not self.web_enabled:
                return ToolResult(False, "Web downloads are disabled.")
            try:
                safe_url = validate_public_http_url(source)
                response = requests.get(safe_url, timeout=30)
                response.raise_for_status()
                destination.write_bytes(response.content)
                return ToolResult(True, f"Downloaded resource to {destination}", {"path": str(destination), "url": safe_url})
            except (ValueError, requests.RequestException, OSError) as exc:
                return ToolResult(False, f"Download failed: {exc}")
        try:
            src_path = resolve_within_root(state_workspace_root(state), source, must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Source not found or not allowed: {exc}")
        try:
            shutil.copy2(src_path, destination)
        except OSError as exc:
            return ToolResult(False, f"Copy failed: {exc}")
        return ToolResult(True, f"Copied resource to {destination}", {"path": str(destination)})
