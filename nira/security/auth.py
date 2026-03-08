from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from nira_agent.automation.models import ToolCall
from nira_agent.automation.permissions import ADMIN, DESTRUCTIVE, READ_ONLY, STANDARD, PermissionLevel


@dataclass
class AuthResult:
    allowed: bool
    reason: str


class VoiceVerifier:
    """Voice verification placeholder with deterministic interface."""

    def verify(self) -> AuthResult:
        return AuthResult(False, "Voice verification is not implemented; passphrase fallback required.")


class PassphraseAuth:
    def __init__(self, env_key: str = "NIRA_PASSPHRASE") -> None:
        self.env_key = env_key
        self.dir = Path.home() / ".nira_agent" / "security"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hash_file = self.dir / "passphrase.hash"
        self.salt_file = self.dir / "passphrase.salt"
        self._seed_from_env()

    def _seed_from_env(self) -> None:
        env = os.getenv(self.env_key)
        if env and not self.hash_file.exists():
            self.set_passphrase(env)

    def set_passphrase(self, passphrase: str) -> None:
        salt = os.urandom(16)
        self.salt_file.write_bytes(salt)
        digest = sha256(salt + passphrase.encode("utf-8")).hexdigest()
        self.hash_file.write_text(digest, encoding="utf-8")

    def verify(self, candidate: str | None) -> AuthResult:
        if not self.hash_file.exists() or not self.salt_file.exists():
            return AuthResult(False, "Passphrase is not configured.")
        if not candidate:
            return AuthResult(False, "Passphrase is required.")
        salt = self.salt_file.read_bytes()
        expected = self.hash_file.read_text(encoding="utf-8").strip()
        actual = sha256(salt + candidate.encode("utf-8")).hexdigest()
        if actual == expected:
            return AuthResult(True, "Passphrase accepted.")
        return AuthResult(False, "Invalid passphrase.")


class SecurityTierEnforcer:
    def __init__(self, current_tier: str = "standard") -> None:
        self.current_tier = current_tier.lower().strip()
        self._tiers = {
            "read_only": READ_ONLY,
            "standard": STANDARD,
            "destructive": DESTRUCTIVE,
            "admin": ADMIN,
        }

    def current(self) -> PermissionLevel:
        return self._tiers.get(self.current_tier, STANDARD)

    def check_level(self, required: PermissionLevel) -> AuthResult:
        current = self.current()
        if current.rank >= required.rank:
            return AuthResult(True, "Permission tier satisfied.")
        return AuthResult(False, f"Tier '{current.name}' cannot execute '{required.name}' actions.")

    def confirm_dangerous(self, call: ToolCall, passphrase_auth: PassphraseAuth, provided_passphrase: str | None) -> AuthResult:
        if call.tool in {"delete_file", "close_app"}:
            return passphrase_auth.verify(provided_passphrase)
        return AuthResult(True, "No additional confirmation needed.")

