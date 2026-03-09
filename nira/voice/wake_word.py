from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from nira.voice.speech_to_text import LocalSpeechToText


@dataclass
class WakeWordStatus:
    enabled: bool
    available: bool
    message: str


class WakeWordDetector:
    """Wake-word detector interface.

    Local-first behavior:
    - Uses lightweight chunked local STT to detect a keyword without API keys.
    - Runs on a background thread and calls the provided callback when the
      keyword appears in captured speech.
    """

    def __init__(self, enabled: bool, keyword: str = "nira", listen_seconds: int = 2) -> None:
        self.enabled = enabled
        self.keyword = keyword
        self.listen_seconds = max(2, listen_seconds)
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = WakeWordStatus(enabled=enabled, available=False, message="Wake word disabled.")
        self._stt: LocalSpeechToText | None = None
        self._on_detected: Callable[[], None] | None = None

    def start(self, on_detected: Callable[[], None]) -> WakeWordStatus:
        if not self.enabled:
            self._status = WakeWordStatus(False, False, "Wake word disabled in config.")
            return self._status
        if self._thread and self._thread.is_alive():
            return self._status
        self._stop_event.clear()
        self._on_detected = on_detected
        if self._stt is None:
            try:
                self._stt = LocalSpeechToText(engine="faster_whisper", listen_seconds=self.listen_seconds)
            except Exception as exc:
                self._status = WakeWordStatus(True, False, f"Wake word STT unavailable: {exc}")
                return self._status
        if not self._stt.is_available():
            self._status = WakeWordStatus(True, False, self._stt.status())
            return self._status
        self._status = WakeWordStatus(True, True, f"Wake word active for '{self.keyword}'.")
        self._thread = threading.Thread(target=self._run_loop, name="nira-wake-word", daemon=True)
        self._thread.start()
        return self._status

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None

    @property
    def status(self) -> WakeWordStatus:
        return self._status

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._stt is None:
                break
            result = self._stt.transcribe_once()
            if self._stop_event.is_set():
                break
            if result.ok and self.keyword.lower() in result.text.lower():
                callback = self._on_detected
                if callback is not None:
                    try:
                        callback()
                    except Exception:
                        pass
                time.sleep(0.3)
                continue
            if not result.ok and result.message:
                self._status = WakeWordStatus(self.enabled, self._status.available, result.message)
            time.sleep(0.2)
