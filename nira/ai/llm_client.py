from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests


logger = logging.getLogger(__name__)


@dataclass
class LLMTextResult:
    ok: bool
    text: str
    provider: str
    error: str = ""


class LocalLlamaClient:
    def __init__(
        self,
        base_url: str,
        timeout_sec: int = 180,
        model: Optional[str] = None,
        max_tokens: int = 160,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self._request_timeout = (5, timeout_sec)
        self.model = model
        self.max_tokens = max(32, int(max_tokens))
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def generate(self, system_prompt: str, user_prompt: str) -> LLMTextResult:
        # Prefer OpenAI-compatible route, fallback to /completion.
        chat_result = self._chat(system_prompt, user_prompt)
        if chat_result.ok:
            return chat_result
        # If chat endpoint timed out, avoid doubling latency with completion fallback.
        if "timed out" in chat_result.error.lower():
            return chat_result
        completion_result = self._completion(system_prompt, user_prompt)
        if completion_result.ok:
            return completion_result
        return LLMTextResult(
            ok=False,
            text="",
            provider="local",
            error=f"chat failed: {chat_result.error}; completion failed: {completion_result.error}",
        )

    def _chat(self, system_prompt: str, user_prompt: str) -> LLMTextResult:
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": self.max_tokens,
        }
        if self.model:
            payload["model"] = self.model
        try:
            response = self._session.post(url, json=payload, timeout=self._request_timeout)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            text = (
                first_choice
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return LLMTextResult(False, "", "local", "Empty chat response.")
            return LLMTextResult(True, text, "local")
        except requests.Timeout:
            return LLMTextResult(False, "", "local", "Local chat request timed out.")
        except Exception as exc:
            logger.debug("Local chat endpoint failed: %s", exc)
            return LLMTextResult(False, "", "local", str(exc))

    def _completion(self, system_prompt: str, user_prompt: str) -> LLMTextResult:
        url = f"{self.base_url}/completion"
        payload = {
            "prompt": f"{system_prompt}\nUser: {user_prompt}\nAssistant(JSON):",
            "temperature": 0.2,
            "n_predict": self.max_tokens,
        }
        try:
            response = self._session.post(url, json=payload, timeout=self._request_timeout)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            text = str(data.get("content") or first_choice.get("text", "")).strip()
            if not text:
                return LLMTextResult(False, "", "local", "Empty completion response.")
            return LLMTextResult(True, text, "local")
        except requests.Timeout:
            return LLMTextResult(False, "", "local", "Local completion request timed out.")
        except Exception as exc:
            return LLMTextResult(False, "", "local", str(exc))


class CloudFallbackClient:
    def __init__(self, endpoint: str | None, api_key: str | None, timeout_sec: int = 45) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self._request_timeout = (5, timeout_sec)
        self._session = requests.Session()

    def close(self) -> None:
        self._session.close()

    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> LLMTextResult:
        if not self.is_configured():
            return LLMTextResult(False, "", "cloud", "Cloud fallback not configured.")

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }
        try:
            response = self._session.post(
                str(self.endpoint),
                json=payload,
                headers=headers,
                timeout=self._request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            text = (
                first_choice
                .get("message", {})
                .get("content", "")
                .strip()
            )
            if not text:
                return LLMTextResult(False, "", "cloud", "Empty cloud response.")
            return LLMTextResult(True, text, "cloud")
        except requests.Timeout:
            return LLMTextResult(False, "", "cloud", "Cloud request timed out.")
        except Exception as exc:
            return LLMTextResult(False, "", "cloud", str(exc))
