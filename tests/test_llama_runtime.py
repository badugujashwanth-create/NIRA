from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from nira.models.llama_runtime import LocalModel


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("http error")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.health_calls = 0

    def get(self, url, timeout=0):
        self.health_calls += 1
        return FakeResponse(200, {"data": []})

    def post(self, url, json=None, timeout=0):
        if url.endswith("/v1/chat/completions"):
            return FakeResponse(200, {"choices": [{"message": {"content": "hello"}}]})
        if url.endswith("/v1/embeddings"):
            return FakeResponse(200, {"data": [{"embedding": [1.0, 2.0]}]})
        return FakeResponse(200, {"content": "fallback"})

class FakeOllamaSession:
    def get(self, url, timeout=0):
        if url.endswith("/api/tags"):
            return FakeResponse(200, {"models": [{"name": "gemma3"}]})
        return FakeResponse(404)

    def post(self, url, json=None, timeout=0):
        if url.endswith("/v1/chat/completions"):
            return FakeResponse(404)
        if url.endswith("/api/chat"):
            return FakeResponse(200, {"message": {"content": "local ollama response"}})
        if url.endswith("/api/embed"):
            return FakeResponse(200, {"embeddings": [[0.1, 0.2]]})
        return FakeResponse(404)


class LlamaRuntimeTests(unittest.TestCase):
    def test_generate_uses_chat_endpoint(self) -> None:
        model = LocalModel(base_url="http://127.0.0.1:8080")
        model._session = FakeSession()
        response = model.generate("test")
        self.assertEqual(response.text, "hello")

    def test_embed_text_returns_vector(self) -> None:
        model = LocalModel(base_url="http://127.0.0.1:8080")
        model._session = FakeSession()
        embedding = model.embed_text("abc")
        self.assertEqual(embedding, [1.0, 2.0])

    def test_managed_start_uses_llama_server(self) -> None:
        with patch("nira.models.llama_runtime.LlamaCppServer") as server_cls:
            instance = server_cls.return_value
            model = LocalModel(
                base_url="http://127.0.0.1:8080",
                manage_server=True,
                llama_dir="local_llm/runtime",
                model_path="local_llm/models/model.gguf",
            )
            model._session = Mock()
            model._session.get.side_effect = [
                requests.RequestException("down"),
                requests.RequestException("down"),
                requests.RequestException("down"),
            ]
            instance.start.return_value = None
            model.start()
            instance.start.assert_called_once()

    def test_ollama_availability_generation_and_embedding(self) -> None:
        model = LocalModel(base_url="http://127.0.0.1:11434", model="gemma3")
        model._session = FakeOllamaSession()
        status = model.availability()
        response = model.generate("test")
        embedding = model.embed_text("test")
        self.assertTrue(status["available"])
        self.assertTrue(status["model_available"])
        self.assertEqual(response.provider, "ollama:gemma3")
        self.assertEqual(response.text, "local ollama response")
        self.assertEqual(embedding, [0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
