from __future__ import annotations

from pathlib import Path

from nira.core.path_utils import PathSecurityError, resolve_within_root
from nira.documents.pdf_processor import PDFProcessor


class TextExtractor:
    def __init__(self, pdf_processor: PDFProcessor | None = None) -> None:
        self.pdf_processor = pdf_processor or PDFProcessor()

    def extract(self, path: str | Path, root: Path | None = None) -> str:
        try:
            candidate = resolve_within_root(root or Path.cwd(), str(path), must_exist=False) if root else Path(path).expanduser()
        except (PathSecurityError, OSError):
            return ""
        if not candidate.exists():
            return ""
        if candidate.suffix.lower() == ".pdf":
            return self.pdf_processor.extract_text(candidate)
        if candidate.suffix.lower() not in {".md", ".txt", ".rst", ".py", ".json", ".toml", ".yaml", ".yml"}:
            return ""
        try:
            return candidate.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            return ""

    def iter_text_candidates(self, root: Path) -> list[Path]:
        patterns = ("*.md", "*.txt", "*.rst", "*.py", "*.json", "*.toml", "*.yaml", "*.yml", "*.pdf")
        candidates: list[Path] = []
        for pattern in patterns:
            try:
                candidates.extend(root.rglob(pattern))
            except OSError:
                continue
        return candidates[:80]
