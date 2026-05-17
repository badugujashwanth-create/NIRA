from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol


class Embedder(Protocol):
    def encode(self, text: str, normalize_embeddings: bool = True) -> list[float]:
        """Encode text to an embedding vector."""


class EmbeddingProvider:
    """BGE-small embedding wrapper with a tiny deterministic fallback."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dimensions: int = 384) -> None:
        self.model_name = model_name
        self.dimensions = dimensions
        self._model = None

    def embed(self, text: str) -> list[float]:
        """Return a normalized embedding vector."""

        model = self._load_model()
        if model is not None:
            vector = model.encode(text, normalize_embeddings=True)
            if hasattr(vector, "tolist"):
                return list(vector.tolist())
            return list(vector)
        return self._hash_embedding(text)

    def _load_model(self):
        if self._model is False:
            return None
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self._model = False
            return None
        self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def _hash_embedding(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\w+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]
