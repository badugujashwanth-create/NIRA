from __future__ import annotations

import re
from html.parser import HTMLParser


SPACE_PATTERN = re.compile(r"\s+")
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._chunks.append(text)

    def get_text(self) -> str:
        return " ".join(self._chunks)


class ContentParser:
    def extract_text(self, html_content: str) -> str:
        extractor = _TextExtractor()
        extractor.feed(html_content)
        return SPACE_PATTERN.sub(" ", extractor.get_text()).strip()

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        sentences = [sentence.strip() for sentence in SENTENCE_PATTERN.split(text) if sentence.strip()]
        return " ".join(sentences[: max(1, max_sentences)])
