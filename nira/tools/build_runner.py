from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolResult


class BuildRunner(Tool):
    name = "run_build"
    description = "Run a local build, compile, or test command."

    def __init__(self, timeout_sec: int = 180) -> None:
        self.timeout_sec = timeout_sec

    def run(self, args: dict[str, Any], state) -> ToolResult:
        try:
            cwd = resolve_within_root(state_workspace_root(state), str(args.get("cwd", ".")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Invalid build directory: {exc}")
        command = str(args.get("command") or self._detect_command(cwd))
        try:
            command_args = command if os.name == "nt" else shlex.split(command, posix=False)
        except ValueError as exc:
            return ToolResult(False, f"Invalid build command: {exc}", {"command": command})
        if not command_args:
            return ToolResult(False, "Build command is empty.", {"command": command})
        try:
            completed = subprocess.run(
                command_args,
                cwd=str(cwd),
                shell=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, f"Build command timed out after {self.timeout_sec}s", {"command": command})
        except OSError as exc:
            return ToolResult(False, f"Build command failed to start: {exc}", {"command": command})
        output = (completed.stdout + "\n" + completed.stderr).strip()
        ok = completed.returncode == 0
        return ToolResult(ok, output or f"Command finished with code {completed.returncode}", {"command": command, "returncode": completed.returncode})

    @staticmethod
    def _detect_command(cwd: Path) -> str:
        return "python -m compileall ."
