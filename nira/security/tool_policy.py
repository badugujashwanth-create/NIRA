from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nira.tools.base import ToolAccess


ApprovalCallback = Callable[[str, dict[str, Any], ToolAccess], bool]


@dataclass
class ToolPermissionPolicy:
    """Default-deny policy for tool side effects.

    Read-only inspection and NIRA's own local state are allowed by default.
    Workspace writes, process execution, and network access require either an
    explicit process-level grant or a per-action approval callback.
    """

    allowed: set[ToolAccess] = field(default_factory=lambda: {ToolAccess.READ, ToolAccess.STATE})
    approval_callback: ApprovalCallback | None = None

    def authorize(self, tool_name: str, args: dict[str, Any], access: ToolAccess) -> tuple[bool, str]:
        if access in self.allowed:
            return True, "allowed_by_policy"
        if self.approval_callback is not None:
            try:
                if self.approval_callback(tool_name, dict(args), access):
                    return True, "approved_once"
            except (EOFError, KeyboardInterrupt):
                return False, "approval_interrupted"
        return False, f"{access.value}_approval_required"

    def grant(self, *access_levels: ToolAccess) -> None:
        self.allowed.update(access_levels)

    def revoke(self, *access_levels: ToolAccess) -> None:
        self.allowed.difference_update(access_levels)
