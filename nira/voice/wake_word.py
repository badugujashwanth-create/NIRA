from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class WakeWordStatus:
    enabled: bool
    available: bool
    message: str


class WakeWordDetector:
    """Wake-word detector interface.

    V1 behavior:
    - Optional Porcupine integration if installed and access key exists.
    - Push-to-talk hotkey remains the primary path.
    """

    def __init__(self, enabled: bool, keyword: str = "nira") -> None:
        self.enabled = enabled
        self.keyword = keyword
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = WakeWordStatus(enabled=enabled, available=False, message="Wake word disabled.")

    def start(self, on_detected: Callable[[], None]) -> WakeWordStatus:
        if not self.enabled:
            self._status = WakeWordStatus(False, False, "Wake word disabled in config.")
            return self._status

        access_key = os.getenv("PV_ACCESS_KEY")
        if not access_key:
            self._status = WakeWordStatus(True, False, "Porcupine key missing; using push-to-talk fallback.")
            return self._status

        try:
            import pvporcupine  # type: ignore

            _ = pvporcupine  # Keep import from being marked unused.
            self._status = WakeWordStatus(
                True,
                False,
                "Porcupine integration placeholder is present; V1 wake-word runtime loop TODO.",
            )
        except Exception:
            self._status = WakeWordStatus(True, False, "Porcupine package not installed.")
        return self._status

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    @property
    def status(self) -> WakeWordStatus:
        return self._status

