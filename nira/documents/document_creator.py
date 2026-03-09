from __future__ import annotations

from pathlib import Path

from nira.core.path_utils import resolve_within_root, sanitize_filename


class DocumentCreator:
    def __init__(self, model, output_dir: Path) -> None:
        self.model = model
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def create(self, filename: str, instructions: str) -> Path:
        target = resolve_within_root(self.output_dir, sanitize_filename(filename, default="document.md"))
        content = instructions
        if self.model:
            prompt = f"Create a local document draft based on:\n{instructions}"
            try:
                result = self.model.generate(prompt)
                generated = getattr(result, "text", "").strip()
                if generated:
                    content = generated
            except Exception:
                content = instructions
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise OSError(f"Could not write document {target}: {exc}") from exc
        return target
