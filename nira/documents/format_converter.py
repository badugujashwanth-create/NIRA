from __future__ import annotations

from pathlib import Path

from nira.core.path_utils import resolve_within_root
from nira.documents.pdf_processor import PDFProcessor


class FormatConverter:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_processor = PDFProcessor()

    def convert(self, source: str, destination: str) -> Path:
        src = resolve_within_root(self.base_dir, source, must_exist=True)
        dst = resolve_within_root(self.base_dir, destination)
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            if src.suffix.lower() == ".pdf":
                dst.write_text(self.pdf_processor.extract_text(src), encoding="utf-8")
                return dst
            if src.suffix.lower() not in {".md", ".txt", ".rst", ".json", ".toml", ".yaml", ".yml"}:
                raise ValueError(f"Unsupported non-text conversion source: {src.suffix}")
            dst.write_text(src.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            return dst
        except OSError as exc:
            raise OSError(f"Document conversion failed: {exc}") from exc
