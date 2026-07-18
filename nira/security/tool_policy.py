from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from nira.tools.base import ToolAccess


ApprovalCallback = Callable[[str, dict[str, Any], ToolAccess], bool]


@dataclass(frozen=True)
class PermissionDecision:
    timestamp: str
    tool: str
    access: str
    allowed: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ToolPermissionPolicy:
    """Default-deny policy for tool side effects.

    Read-only inspection and NIRA's own local state are allowed by default.
    Workspace writes, process execution, and network access require either an
    explicit process-level grant or a per-action approval callback.
    """

    allowed: set[ToolAccess] = field(default_factory=lambda: {ToolAccess.READ, ToolAccess.STATE})
    approval_callback: ApprovalCallback | None = None
    _decisions: deque[PermissionDecision] = field(default_factory=lambda: deque(maxlen=100), init=False)

    def authorize(self, tool_name: str, args: dict[str, Any], access: ToolAccess) -> tuple[bool, str]:
        if access in self.allowed:
            return self._decide(tool_name, access, True, "allowed_by_policy")
        if self.approval_callback is not None:
            try:
                if self.approval_callback(tool_name, dict(args), access):
                    return self._decide(tool_name, access, True, "approved_once")
            except (EOFError, KeyboardInterrupt):
                return self._decide(tool_name, access, False, "approval_interrupted")
            except Exception:
                return self._decide(tool_name, access, False, "approval_callback_failed")
        return self._decide(tool_name, access, False, f"{access.value}_approval_required")

    def grant(self, *access_levels: ToolAccess) -> None:
        self.allowed.update(access_levels)

    def revoke(self, *access_levels: ToolAccess) -> None:
        self.allowed.difference_update(access_levels)

    def recent_decisions(self, limit: int = 20) -> list[dict[str, object]]:
        return [item.to_dict() for item in list(self._decisions)[-max(1, min(limit, 100)) :]]

    def _decide(self, tool_name: str, access: ToolAccess, allowed: bool, reason: str) -> tuple[bool, str]:
        self._decisions.append(
            PermissionDecision(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                tool=tool_name,
                access=access.value,
                allowed=allowed,
                reason=reason,
            )
        )
        return allowed, reason
