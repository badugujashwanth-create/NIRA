from __future__ import annotations

from nira.voice.speech_to_text import LocalSpeechToText
from nira.voice.tts import LocalTTS


class VoiceInterface:
    def __init__(self, enabled: bool = False, tts_enabled: bool = True) -> None:
        self.enabled = enabled
        self.tts_enabled = tts_enabled
        self.available = False
        self.tts_available = False
        self._status = "voice disabled"
        self._stt: LocalSpeechToText | None = None
        self._tts: LocalTTS | None = None
        if enabled:
            self._initialize()

    def _initialize(self) -> None:
        try:
            stt = LocalSpeechToText(engine="faster_whisper")
            if stt.is_available():
                self._stt = stt
                self.available = True
                self._status = stt.status()
            else:
                self._status = stt.status()
        except Exception as exc:
            self._status = f"STT unavailable: {exc}"
        if self.tts_enabled:
            try:
                tts = LocalTTS()
                if tts.is_available():
                    self._tts = tts
                    self.tts_available = True
            except Exception:
                self._tts = None
                self.tts_available = False

    def status(self) -> str:
        if self.available:
            suffix = " + TTS" if self.tts_available else ""
            return f"{self._status}{suffix}"
        return self._status

    def listen_once(self) -> str:
        if not self.enabled or not self.available or self._stt is None:
            return ""
        result = self._stt.transcribe_once()
        if not result.ok:
            self._status = result.message
            return ""
        return result.text.strip()

    def speak(self, text: str) -> bool:
        if not self.enabled or not self.tts_available or self._tts is None:
            return False
        result = self._tts.speak(text)
        return result.ok
