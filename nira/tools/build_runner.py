from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root, state_workspace_root
from nira.tools.base import Tool, ToolAccess, ToolResult


class BuildRunner(Tool):
    name = "run_build"
    description = "Run one allowlisted local diagnostic profile."
    access = ToolAccess.PROCESS

    _profiles = {
        "python_compile": ("-m", "compileall", "-q"),
        "python_tests": ("-m", "pytest", "-q"),
    }

    def __init__(self, timeout_sec: int = 180) -> None:
        self.timeout_sec = timeout_sec

    def run(self, args: dict[str, Any], state) -> ToolResult:
        try:
            cwd = resolve_within_root(state_workspace_root(state), str(args.get("cwd", ".")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Invalid build directory: {exc}")
        profile = str(args.get("profile", "")).strip() or self._detect_profile(cwd)
        command_args = self._command_for_profile(profile, cwd)
        if command_args is None:
            return ToolResult(
                False,
                f"Unsupported diagnostic profile: {profile or 'none'}",
                {
                    "profile": profile,
                    "allowed_profiles": sorted(self._profiles),
                    "arbitrary_commands_allowed": False,
                },
            )
        command = subprocess.list2cmdline(command_args)
        cancel_event = getattr(state, "context", {}).get("cancel_event")
        try:
            process = subprocess.Popen(
                command_args,
                cwd=str(cwd),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            return ToolResult(False, f"Build command failed to start: {exc}", {"command": command})
        deadline = time.monotonic() + self.timeout_sec
        while True:
            if cancel_event is not None and cancel_event.is_set():
                process.terminate()
                stdout, stderr = process.communicate(timeout=5)
                output = (stdout + "\n" + stderr).strip()
                return ToolResult(
                    False,
                    output or "Diagnostic cancelled by the user.",
                    {
                        "profile": profile,
                        "command": command,
                        "returncode": process.returncode,
                        "verified": False,
                        "cancelled": True,
                    },
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.communicate()
                return ToolResult(
                    False,
                    f"Diagnostic timed out after {self.timeout_sec}s",
                    {"profile": profile, "command": command, "verified": False, "timed_out": True},
                )
            try:
                stdout, stderr = process.communicate(timeout=min(0.1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        output = (stdout + "\n" + stderr).strip()
        ok = process.returncode == 0
        return ToolResult(
            ok,
            output or f"Diagnostic finished with code {process.returncode}",
            {
                "profile": profile,
                "command": command,
                "returncode": process.returncode,
                "verified": ok,
            },
        )

    @classmethod
    def _command_for_profile(cls, profile: str, cwd: Path) -> list[str] | None:
        suffix = cls._profiles.get(profile)
        if suffix is None:
            return None
        command = [sys.executable, *suffix]
        if profile == "python_compile":
            source_targets = [
                name
                for name in ("src", "app", "nira", "nira_agent", "local_llm")
                if (cwd / name).is_dir()
            ]
            if not source_targets:
                source_targets = sorted(path.name for path in cwd.glob("*.py"))[:20] or ["."]
            command.extend(source_targets)
        return command

    @staticmethod
    def _detect_profile(cwd: Path) -> str:
        if (cwd / "pyproject.toml").exists() or (cwd / "requirements.txt").exists():
            return "python_compile"
        return ""
