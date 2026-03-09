from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from nira.core.text_utils import chunk_text


@dataclass
class PDFExtraction:
    text: str
    page_count: int
    path: str


class PDFProcessor:
    def extract(self, path: str | Path) -> PDFExtraction:
        candidate = Path(path).expanduser()
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(candidate))
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            return PDFExtraction(text=text, page_count=len(reader.pages), path=str(candidate))
        except (ImportError, OSError, ValueError):
            return PDFExtraction(text="", page_count=0, path=str(candidate))

    def extract_text(self, path: str | Path) -> str:
        return self.extract(path).text

    def chunk_text(self, text: str, chunk_size: int = 1200) -> list[str]:
        return chunk_text(text, chunk_size=chunk_size, overlap=min(120, max(0, chunk_size // 10)))
