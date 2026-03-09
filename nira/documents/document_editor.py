from __future__ import annotations

from pathlib import Path

from nira.core.path_utils import resolve_within_root


class DocumentEditorService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def write(self, path: str, content: str, append: bool = False) -> Path:
        target = resolve_within_root(self.base_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
        return target
