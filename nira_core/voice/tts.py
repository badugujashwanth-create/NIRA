from __future__ import annotations

import asyncio
from pathlib import Path


class PiperTTS:
    """Optional Piper TTS wrapper for local speech synthesis."""

    def __init__(self, executable: str = "piper") -> None:
        self.executable = executable

    async def synthesize(self, text: str, model_path: Path, output_path: Path) -> Path:
        """Synthesize speech with Piper if installed."""

        process = await asyncio.create_subprocess_exec(
            self.executable,
            "--model",
            str(model_path),
            "--output_file",
            str(output_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(text.encode("utf-8"))
        if process.returncode != 0:
            raise RuntimeError(stderr.decode(errors="replace") or stdout.decode(errors="replace"))
        return output_path
