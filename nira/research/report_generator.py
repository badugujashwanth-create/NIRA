from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from nira.core.path_utils import resolve_within_root, safe_slug, sanitize_filename


@dataclass
class ResearchReport:
    title: str
    overview: str
    key_methods: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    path: str = ""
    content: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "overview": self.overview,
            "key_methods": list(self.key_methods),
            "recommendations": list(self.recommendations),
            "references": list(self.references),
            "path": self.path,
            "content": self.content,
        }


class ReportGenerator:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_markdown(self, filename: str, content: str) -> Path:
        target = resolve_within_root(self.output_dir, sanitize_filename(filename, default="research_report.md"))
        try:
            target.write_text(str(content or "") + ("" if str(content or "").endswith("\n") else "\n"), encoding="utf-8")
        except OSError as exc:
            raise OSError(f"Could not write research report {target}: {exc}") from exc
        return target

    def generate(
        self,
        topic: str,
        overview: str,
        key_methods: list[str],
        recommendations: list[str],
        references: list[str],
    ) -> ResearchReport:
        title = topic.title()
        body = [
            f"Title: {title}",
            "",
            "Overview:",
            overview.strip() or "No overview available.",
            "",
            "Key Methods:",
            *[f"- {item}" for item in key_methods],
            "",
            "Recommendations:",
            *[f"- {item}" for item in recommendations],
            "",
            "References:",
            *[f"- {item}" for item in references],
        ]
        content = "\n".join(body).strip() + "\n"
        slug = safe_slug(title, default="research_report", max_length=60)
        target = self.write_markdown(f"{slug}.md", content)
        return ResearchReport(
            title=title,
            overview=overview,
            key_methods=key_methods,
            recommendations=recommendations,
            references=references,
            path=str(target),
            content=content,
        )
