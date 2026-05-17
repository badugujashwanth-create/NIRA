"""CPU-oriented voice layer."""

from nira_core.voice.transcription import FasterWhisperTranscriber
from nira_core.voice.tts import PiperTTS

__all__ = ["FasterWhisperTranscriber", "PiperTTS"]
