from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from local_llm.llama_cpp_server import LlamaCppServer, LlamaServerConfig, ServerStartError


@dataclass
class ModelResponse:
    text: str
    provider: str = "llama.cpp"
    raw: dict[str, Any] | None = None


class LocalModel:
    def __init__(
        self,
        *,
        base_url: str,
        model: str | None = None,
        timeout_sec: int = 120,
        manage_server: bool = False,
        llama_dir: str | None = None,
        model_path: str | None = None,
        startup_timeout_sec: int = 120,
        max_tokens: int = 512,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec
        self.manage_server = manage_server
        self.llama_dir = Path(llama_dir).expanduser().resolve() if llama_dir else None
        self.model_path = Path(model_path).expanduser().resolve() if model_path else None
        self.startup_timeout_sec = startup_timeout_sec
        self.max_tokens = max(64, max_tokens)
        self._session = requests.Session()
        self._server: LlamaCppServer | None = None
        self._request_timeout = max(5, timeout_sec)

    def start(self) -> None:
        if self.is_ready():
            return
        if not self.manage_server:
            return
        if self._server is not None:
            return
        if not self.llama_dir or not self.model_path:
            raise ServerStartError("Managed llama.cpp startup requires both llama_dir and model_path.")
        config = LlamaServerConfig(
            llama_dir=self.llama_dir,
            model_path=self.model_path,
            startup_timeout_sec=self.startup_timeout_sec,
        )
        self._server = LlamaCppServer(config)
        self._server.start()

    def close(self) -> None:
        try:
            self._session.close()
        finally:
            if self._server is not None:
                self._server.stop()
                self._server = None

    def is_ready(self) -> bool:
        for endpoint in ("/health", "/v1/models"):
            try:
                response = self._session.get(f"{self.base_url}{endpoint}", timeout=3)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                continue
        return False

    def generate(self, prompt: str) -> ModelResponse:
        self.start()
        if not self.is_ready():
            return ModelResponse(text="", raw={"error": "local model unavailable"})
        result = self._chat(prompt)
        if result.text:
            return result
        completion = self._completion(prompt)
        if completion.text:
            return completion
        return ModelResponse(text="", raw={"error": "local model unavailable"})

    def embed_text(self, text: str) -> list[float] | None:
        self.start()
        if not self.is_ready():
            return None
        for path, payload in (
            ("/v1/embeddings", {"input": text}),
            ("/embedding", {"content": text}),
        ):
            if self.model:
                payload["model"] = self.model
            try:
                response = self._session.post(f"{self.base_url}{path}", json=payload, timeout=self._request_timeout)
                response.raise_for_status()
                data = response.json()
                if "data" in data and data["data"]:
                    embedding = [float(value) for value in data["data"][0].get("embedding", [])]
                    return embedding or None
                if "embedding" in data:
                    embedding = [float(value) for value in data.get("embedding", [])]
                    return embedding or None
            except requests.RequestException:
                continue
        return None

    def _chat(self, prompt: str) -> ModelResponse:
        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
        }
        if self.model:
            payload["model"] = self.model
        try:
            response = self._session.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=(3, self._request_timeout),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            text = str(first_choice.get("message", {}).get("content", "")).strip()
            return ModelResponse(text=text, provider=f"llama.cpp:{self.model or 'default'}", raw=data)
        except requests.RequestException as exc:
            return ModelResponse(text="", provider=f"llama.cpp:{self.model or 'default'}", raw={"error": str(exc)})

    def _completion(self, prompt: str) -> ModelResponse:
        payload = {"prompt": prompt, "temperature": 0.2, "n_predict": self.max_tokens}
        try:
            response = self._session.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=(3, self._request_timeout),
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            text = str(data.get("content") or first_choice.get("text", "")).strip()
            return ModelResponse(text=text, provider=f"llama.cpp:{self.model or 'default'}", raw=data)
        except requests.RequestException as exc:
            return ModelResponse(text="", provider=f"llama.cpp:{self.model or 'default'}", raw={"error": str(exc)})
