from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import sounddevice as sd

    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False


@dataclass
class STTResult:
    ok: bool
    text: str
    message: str


class LocalSpeechToText:
    def __init__(
        self,
        engine: str,
        listen_seconds: int = 5,
        sample_rate: int = 16000,
        whisper_model_name: str = "base.en",
        vosk_model_path: Optional[str] = None,
    ) -> None:
        self.engine = engine.lower().strip()
        self.listen_seconds = max(2, listen_seconds)
        self.sample_rate = sample_rate
        self.whisper_model_name = whisper_model_name
        self.vosk_model_path = vosk_model_path
        self._fw_model = None
        self._vosk_model = None
        self._status = "ready"
        self._active_engine = self.engine
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        if not SOUNDDEVICE_AVAILABLE:
            self._status = "sounddevice package missing."
            return

        if self.engine == "faster_whisper":
            if self._init_faster_whisper():
                self._active_engine = "faster_whisper"
                return
            if self._init_vosk():
                self._active_engine = "vosk"
                self._status = "faster-whisper unavailable; using vosk fallback."
                return
        elif self.engine == "vosk":
            if self._init_vosk():
                self._active_engine = "vosk"
                return
            if self._init_faster_whisper():
                self._active_engine = "faster_whisper"
                self._status = "vosk unavailable; using faster-whisper fallback."
                return

        self._status = "No STT backend available."

    def _init_faster_whisper(self) -> bool:
        try:
            from faster_whisper import WhisperModel  # type: ignore

            self._fw_model = WhisperModel(
                self.whisper_model_name,
                device="cpu",
                compute_type="int8",
            )
            return True
        except Exception:
            self._fw_model = None
            return False

    def _init_vosk(self) -> bool:
        try:
            from vosk import Model  # type: ignore
        except Exception:
            self._vosk_model = None
            return False
        if not self.vosk_model_path:
            self._vosk_model = None
            return False
        try:
            self._vosk_model = Model(self.vosk_model_path)
            return True
        except Exception:
            self._vosk_model = None
            return False

    def is_available(self) -> bool:
        return self._fw_model is not None or self._vosk_model is not None

    def status(self) -> str:
        if self.is_available():
            return f"active engine: {self._active_engine}"
        return self._status

    def transcribe_once(self) -> STTResult:
        if not self.is_available():
            return STTResult(False, "", self.status())
        audio = self._record_audio()
        if audio is None:
            return STTResult(False, "", "Microphone capture failed.")

        if self._active_engine == "faster_whisper" and self._fw_model is not None:
            return self._transcribe_faster_whisper(audio)
        if self._active_engine == "vosk" and self._vosk_model is not None:
            return self._transcribe_vosk(audio)
        return STTResult(False, "", "STT engine unavailable.")

    def _record_audio(self) -> Optional[np.ndarray]:
        if not SOUNDDEVICE_AVAILABLE:
            return None
        try:
            frames = int(self.listen_seconds * self.sample_rate)
            recording = sd.rec(
                frames,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            return np.squeeze(recording)
        except Exception:
            return None

    def _transcribe_faster_whisper(self, audio: np.ndarray) -> STTResult:
        try:
            segments, _ = self._fw_model.transcribe(audio, language="en")  # type: ignore[union-attr]
            text = " ".join(segment.text.strip() for segment in segments).strip()
            if not text:
                return STTResult(False, "", "No speech detected.")
            return STTResult(True, text, "ok")
        except Exception as exc:
            return STTResult(False, "", f"faster-whisper error: {exc}")

    def _transcribe_vosk(self, audio: np.ndarray) -> STTResult:
        try:
            from vosk import KaldiRecognizer  # type: ignore

            recognizer = KaldiRecognizer(self._vosk_model, self.sample_rate)
            pcm16 = (audio * 32767).astype(np.int16).tobytes()
            recognizer.AcceptWaveform(pcm16)
            raw = recognizer.FinalResult()
            payload = json.loads(raw)
            text = payload.get("text", "").strip()
            if not text:
                return STTResult(False, "", "No speech detected.")
            return STTResult(True, text, "ok")
        except Exception as exc:
            return STTResult(False, "", f"vosk error: {exc}")

