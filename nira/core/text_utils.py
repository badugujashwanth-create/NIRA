from __future__ import annotations

import re


def tokenize_terms(text: str, min_length: int = 2) -> list[str]:
    pattern = rf"[a-z0-9_]{{{max(1, min_length)},}}"
    return re.findall(pattern, text.lower())


def chunk_text(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(length, start + chunk_size)
        if end < length:
            boundary = text.rfind(" ", start, end)
            if boundary > start + (chunk_size // 2):
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks
