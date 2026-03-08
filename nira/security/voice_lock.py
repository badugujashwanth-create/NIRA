from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VoiceLockResult:
    authorized: bool
    reason: str


class VoiceLock:
    """Stub interface for future local voice biometric verification."""

    def is_available(self) -> bool:
        return False

    def verify(self, _audio_blob: bytes | None = None) -> VoiceLockResult:
        return VoiceLockResult(
            authorized=False,
            reason="Voice biometric lock is not implemented in V1. Use passphrase gate instead.",
        )

