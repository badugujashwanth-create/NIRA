from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from nira_core.config import ToolConfig


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """A tool execution request that must be authorized before execution."""

    tool_name: str
    action: str
    path: Path | None = None
    command: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PermissionDecision:
    """Allow or deny result with a concrete reason."""

    allowed: bool
    reason: str


class PermissionPolicy:
    """Strict local permission policy for filesystem and shell tools."""

    def __init__(self, config: ToolConfig) -> None:
        self._config = config
        self._workspace = config.workspace_root.resolve()
        self._allowed_commands = set(config.allowed_commands)

    def decide(self, request: ToolRequest) -> PermissionDecision:
        """Authorize a request before sandbox execution."""

        if request.path is not None and not self._is_within_workspace(request.path):
            return PermissionDecision(False, "path_outside_workspace")
        if request.command:
            executable = request.command[0]
            if executable not in self._allowed_commands:
                return PermissionDecision(False, f"command_not_allowed:{executable}")
        if request.action in {"delete", "move"} and request.metadata.get("approved") != "true":
            return PermissionDecision(False, "destructive_action_requires_explicit_approval")
        return PermissionDecision(True, "allowed")

    def _is_within_workspace(self, path: Path) -> bool:
        resolved = path.resolve()
        return resolved == self._workspace or self._workspace in resolved.parents
