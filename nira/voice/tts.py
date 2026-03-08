from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class TTSResult:
    ok: bool
    message: str


class LocalTTS:
    def __init__(self, engine_name: str = "pyttsx3") -> None:
        self.engine_name = engine_name.lower().strip()
        self._engine = None
        self._lock = threading.Lock()
        self._status = "ready"
        self._init_engine()

    def _init_engine(self) -> None:
        if self.engine_name != "pyttsx3":
            self._status = f"Unsupported TTS engine: {self.engine_name}"
            return
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 180)
        except Exception as exc:
            self._status = f"TTS init error: {exc}"
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def status(self) -> str:
        if self.is_available():
            return "active engine: pyttsx3"
        return self._status

    def speak(self, text: str) -> TTSResult:
        if not self._engine:
            return TTSResult(False, self.status())
        body = text.strip()
        if not body:
            return TTSResult(False, "Nothing to speak.")
        with self._lock:
            try:
                self._engine.say(body)
                self._engine.runAndWait()
                return TTSResult(True, "ok")
            except Exception as exc:
                return TTSResult(False, str(exc))

