from __future__ import annotations

from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptChunk:
    """Streaming transcription chunk."""

    text: str
    start: float
    end: float


class FasterWhisperTranscriber:
    """CPU-optimized faster-whisper transcriber using int8 compute."""

    def __init__(self, model_size: str = "base.en", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self._model = None

    async def transcribe_file(self, path: str) -> list[TranscriptChunk]:
        """Transcribe one audio file."""

        model = self._load_model()
        segments, _ = model.transcribe(path, vad_filter=True)
        return [TranscriptChunk(text=segment.text, start=float(segment.start), end=float(segment.end)) for segment in segments]

    async def stream_chunks(self, paths: Iterable[str]) -> AsyncIterator[TranscriptChunk]:
        """Simple file-chunk streaming interface for local pipelines."""

        for path in paths:
            for chunk in await self.transcribe_file(path):
                yield chunk

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Voice transcription requires faster-whisper. Install with: pip install -r requirements.txt") from exc
        self._model = WhisperModel(self.model_size, device="cpu", compute_type=self.compute_type)
        return self._model
