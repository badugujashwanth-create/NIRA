from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from nira_core.config import ToolConfig


@dataclass(frozen=True, slots=True)
class SandboxResult:
    """Result from a sandboxed subprocess execution."""

    ok: bool
    stdout: str
    stderr: str
    returncode: int


class SubprocessSandbox:
    """Restricted subprocess executor using isolated working directories."""

    def __init__(self, config: ToolConfig) -> None:
        self._config = config
        self._workspace = config.workspace_root.resolve()
        self._sandbox_root = config.sandbox_root.resolve()
        self._sandbox_root.mkdir(parents=True, exist_ok=True)

    async def run(self, command: tuple[str, ...], cwd: Path | None = None) -> SandboxResult:
        """Run an allowlisted command without invoking a shell."""

        working_dir = (cwd or self._workspace).resolve()
        if working_dir != self._workspace and self._workspace not in working_dir.parents:
            raise PermissionError(f"Working directory outside workspace: {working_dir}")
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._config.command_timeout_sec)
        except asyncio.TimeoutError:
            process.kill()
            stdout, stderr = await process.communicate()
            return SandboxResult(False, stdout.decode(errors="replace"), "command timed out", -1)
        return SandboxResult(
            ok=process.returncode == 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            returncode=int(process.returncode or 0),
        )
