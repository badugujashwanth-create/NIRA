from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests

from nira.ai.prompts import SYSTEM_PROMPT


@dataclass
class LLMResult:
    ok: bool
    text: str
    source: str


class LlamaCppConnector:
    def __init__(self, base_url: str, model: Optional[str] = None, timeout_sec: int = 45) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_sec = timeout_sec
        self._session = requests.Session()
        self._mode: Optional[str] = None

    def generate(self, prompt: str) -> LLMResult:
        if self._mode == "chat":
            result = self._chat_completion(prompt)
            if result.ok:
                return result
        elif self._mode == "completion":
            result = self._completion(prompt)
            if result.ok:
                return result

        result = self._chat_completion(prompt)
        if result.ok:
            self._mode = "chat"
            return result

        result2 = self._completion(prompt)
        if result2.ok:
            self._mode = "completion"
            return result2

        text = f"LLM endpoint unavailable. Chat: {result.text} | Completion: {result2.text}"
        return LLMResult(ok=False, text=text, source="llama.cpp")

    def _chat_completion(self, prompt: str) -> LLMResult:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        if self.model:
            payload["model"] = self.model
        try:
            response = self._session.post(url, json=payload, timeout=self.timeout_sec)
            response.raise_for_status()
            data = response.json()
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return LLMResult(False, "Empty response from /v1/chat/completions", "llama.cpp")
            return LLMResult(True, text, "llama.cpp")
        except Exception as exc:
            return LLMResult(False, str(exc), "llama.cpp")

    def _completion(self, prompt: str) -> LLMResult:
        url = f"{self.base_url}/completion"
        body = f"{SYSTEM_PROMPT}\nUser: {prompt}\nNIRA:"
        payload = {"prompt": body, "temperature": 0.3, "n_predict": 256}
        try:
            response = self._session.post(url, json=payload, timeout=self.timeout_sec)
            response.raise_for_status()
            data = response.json()
            text = data.get("content") or data.get("choices", [{}])[0].get("text", "")
            text = str(text).strip()
            if not text:
                return LLMResult(False, "Empty response from /completion", "llama.cpp")
            return LLMResult(True, text, "llama.cpp")
        except Exception as exc:
            return LLMResult(False, str(exc), "llama.cpp")

