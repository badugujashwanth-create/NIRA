from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable


@dataclass
class EmotionalSignal:
    label: str
    intensity: float
    expires_at: float


class PersonalityMiddleware:
    """
    Applies tone shaping only.
    Emotional signals never alter tool autonomy or safety decisions.
    """

    def __init__(self, cooldown_sec: int = 12, emotional_ttl_sec: int = 900) -> None:
        self.cooldown_sec = max(3, cooldown_sec)
        self.emotional_ttl_sec = max(60, emotional_ttl_sec)
        self._signals: list[EmotionalSignal] = []
        self._last_reaction_at = 0.0

    def ingest_user_text(self, user_text: str) -> None:
        now = time.time()
        lowered = user_text.lower()
        detected: list[EmotionalSignal] = []
        if any(k in lowered for k in ("urgent", "asap", "immediately", "right now")):
            detected.append(EmotionalSignal("urgency", 0.75, now + self.emotional_ttl_sec))
        if any(k in lowered for k in ("frustrated", "angry", "annoyed", "broken", "failed")):
            detected.append(EmotionalSignal("frustration", 0.80, now + self.emotional_ttl_sec))
        if any(k in lowered for k in ("worried", "nervous", "anxious")):
            detected.append(EmotionalSignal("anxiety", 0.65, now + self.emotional_ttl_sec))
        if detected:
            self._signals.extend(detected)
        self._prune(now)

    def apply(self, response_text: str, tone: str, mode_name: str) -> str:
        now = time.time()
        self._prune(now)
        if not response_text.strip():
            return response_text
        if now - self._last_reaction_at < self.cooldown_sec:
            return response_text

        dominant = self._dominant_signal()
        if dominant is None:
            return response_text

        # Tone-only adaptation: response content/action plan remains unchanged.
        prefix = self._prefix_for_signal(dominant, tone=tone, mode_name=mode_name)
        self._last_reaction_at = now
        if not prefix:
            return response_text
        return f"{prefix} {response_text}".strip()

    def _dominant_signal(self) -> EmotionalSignal | None:
        if not self._signals:
            return None
        return max(self._signals, key=lambda s: s.intensity)

    def _prune(self, now: float) -> None:
        self._signals = [signal for signal in self._signals if signal.expires_at > now]

    @staticmethod
    def _prefix_for_signal(signal: EmotionalSignal, tone: str, mode_name: str) -> str:
        tone_key = (tone or "").lower()
        mode_key = (mode_name or "").lower()
        if signal.label == "urgency":
            return "Quick update:"
        if signal.label == "frustration":
            if "calm" in mode_key or tone_key in {"supportive", "gentle"}:
                return "I hear the frustration."
            return "Stabilization update:"
        if signal.label == "anxiety":
            return "We can take this step-by-step."
        return ""

    def active_signals(self) -> list[str]:
        self._prune(time.time())
        return [s.label for s in self._signals]
