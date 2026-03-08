from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Optional


@dataclass
class PassphraseCheckResult:
    authorized: bool
    reason: str


class PassphraseGate:
    """Optional passphrase gate for dangerous commands."""

    def __init__(self, required: bool, storage_dir: Path) -> None:
        self.required = required
        self.storage_dir = storage_dir.expanduser()
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._hash_path = self.storage_dir / "passphrase.sha256"
        self._salt_path = self.storage_dir / "passphrase.salt"
        self._ensure_seeded_from_env()

    def _ensure_seeded_from_env(self) -> None:
        env_value = os.getenv("NIRA_PASSPHRASE")
        if not self.required or not env_value:
            return
        if self._hash_path.exists() and self._salt_path.exists():
            return
        self.set_passphrase(env_value)

    def set_passphrase(self, passphrase: str) -> None:
        salt = os.urandom(16)
        self._salt_path.write_bytes(salt)
        digest = sha256(salt + passphrase.encode("utf-8")).hexdigest()
        self._hash_path.write_text(digest, encoding="utf-8")

    def has_passphrase(self) -> bool:
        return self._hash_path.exists() and self._salt_path.exists()

    def is_action_dangerous(self, action: str) -> bool:
        return action in {"close_app", "run_script", "delete_file"}

    def authorize(self, action: str, provided_passphrase: Optional[str]) -> PassphraseCheckResult:
        if not self.required or not self.is_action_dangerous(action):
            return PassphraseCheckResult(True, "Passphrase not required.")
        if not self.has_passphrase():
            return PassphraseCheckResult(False, "Passphrase gate enabled but no passphrase is configured.")
        if not provided_passphrase:
            return PassphraseCheckResult(False, "Passphrase required for this command.")
        return self._verify(provided_passphrase)

    def _verify(self, candidate: str) -> PassphraseCheckResult:
        try:
            digest = self._hash_path.read_text(encoding="utf-8").strip()
            salt = self._salt_path.read_bytes()
        except OSError:
            return PassphraseCheckResult(False, "Passphrase storage is unavailable.")
        candidate_digest = sha256(salt + candidate.encode("utf-8")).hexdigest()
        if candidate_digest == digest:
            return PassphraseCheckResult(True, "Passphrase accepted.")
        return PassphraseCheckResult(False, "Invalid passphrase.")

