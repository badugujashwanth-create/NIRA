from __future__ import annotations

import time

from nira_core.config import ModelSpec, RuntimeConfig
from nira_core.inference.base import InferenceBackend, InferenceRequest, InferenceResult, result_from_text


class LlamaCppBackend(InferenceBackend):
    """OpenAI-compatible llama.cpp server adapter for future backend swaps."""

    def __init__(self, runtime: RuntimeConfig) -> None:
        self._runtime = runtime

    async def generate(self, spec: ModelSpec, request: InferenceRequest) -> InferenceResult:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("llama.cpp backend requires httpx. Install with: pip install -r requirements.txt") from exc

        started = time.perf_counter()
        payload = {
            "model": spec.name,
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or spec.num_predict,
            "temperature": spec.temperature if request.temperature is None else request.temperature,
        }
        async with httpx.AsyncClient(base_url=self._runtime.llama_cpp_base_url, timeout=self._runtime.inference_timeout_sec) as client:
            response = await client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return result_from_text(str(text), spec, request.prompt, started, data)

    async def unload(self, spec: ModelSpec) -> None:
        return None
