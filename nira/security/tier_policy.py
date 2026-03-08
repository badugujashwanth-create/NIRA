from __future__ import annotations

from dataclasses import dataclass

from nira_agent.automation.permissions import ADMIN, DESTRUCTIVE, READ_ONLY, STANDARD, PermissionLevel


@dataclass
class TierCheck:
    allowed: bool
    message: str


class TierPolicy:
    _tiers = {
        "read_only": READ_ONLY,
        "standard": STANDARD,
        "destructive": DESTRUCTIVE,
        "admin": ADMIN,
    }

    def __init__(self, current_tier: str = "standard") -> None:
        self.current_tier = self._tiers.get(current_tier, STANDARD)

    def enforce(self, required: PermissionLevel) -> TierCheck:
        if self.current_tier.rank >= required.rank:
            return TierCheck(True, f"Tier '{self.current_tier.name}' allows '{required.name}'.")
        return TierCheck(False, f"Tier '{self.current_tier.name}' blocks '{required.name}'.")

