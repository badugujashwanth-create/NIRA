from __future__ import annotations

import time
from typing import Any

from nira_core.config import ModelSpec, RuntimeConfig
from nira_core.inference.base import InferenceBackend, InferenceRequest, InferenceResult, result_from_text


class OllamaBackend(InferenceBackend):
    """Ollama adapter with CPU-safe defaults and explicit model unloading."""

    def __init__(self, runtime: RuntimeConfig) -> None:
        self._runtime = runtime

    async def generate(self, spec: ModelSpec, request: InferenceRequest) -> InferenceResult:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("Ollama backend requires httpx. Install with: pip install -r requirements.txt") from exc

        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": spec.name,
            "prompt": request.prompt,
            "stream": False,
            "keep_alive": spec.keep_alive,
            "options": {
                "num_ctx": min(spec.context_window, self._runtime.default_context_window),
                "num_predict": request.max_tokens or spec.num_predict,
                "temperature": spec.temperature if request.temperature is None else request.temperature,
            },
        }
        async with httpx.AsyncClient(base_url=self._runtime.ollama_base_url, timeout=self._runtime.inference_timeout_sec) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
        return result_from_text(str(data.get("response", "")), spec, request.prompt, started, data)

    async def unload(self, spec: ModelSpec) -> None:
        try:
            import httpx
        except ImportError:
            return
        payload = {"model": spec.name, "prompt": "", "stream": False, "keep_alive": 0}
        try:
            async with httpx.AsyncClient(base_url=self._runtime.ollama_base_url, timeout=10.0) as client:
                await client.post("/api/generate", json=payload)
        except Exception:
            return
