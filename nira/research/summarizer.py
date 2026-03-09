from __future__ import annotations

from dataclasses import dataclass, field

from nira.core.text_utils import chunk_text


@dataclass
class SummaryResult:
    summary: str
    key_sections: list[str] = field(default_factory=list)
    compressed_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "key_sections": list(self.key_sections),
            "compressed_text": self.compressed_text,
        }


class Summarizer:
    def __init__(self, model) -> None:
        self.model = model

    def summarize(self, text: str, topic: str = "", max_chunk_chars: int = 2400) -> SummaryResult:
        if not text.strip():
            return SummaryResult(summary="")
        chunks = self.chunk_text(text, chunk_size=max_chunk_chars)
        section_summaries = [self._summarize_chunk(chunk, topic) for chunk in chunks[:8]]
        merged_summary = self._merge_summaries(section_summaries, topic)
        key_sections = self.extract_important_sections(text)
        compressed_text = self.compress_for_storage(merged_summary, key_sections)
        return SummaryResult(summary=merged_summary, key_sections=key_sections, compressed_text=compressed_text)

    def chunk_text(self, text: str, chunk_size: int = 2400, overlap: int = 200) -> list[str]:
        return chunk_text(text, chunk_size=chunk_size, overlap=overlap)

    def extract_important_sections(self, text: str, limit: int = 6) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        sections = [line for line in lines if len(line.split()) >= 6]
        if not sections:
            sections = lines[:limit]
        return sections[:limit]

    def compress_for_storage(self, summary: str, key_sections: list[str]) -> str:
        payload = [summary.strip(), "", "Key Sections:", *[f"- {section}" for section in key_sections]]
        return "\n".join(line for line in payload if line is not None).strip()

    def _summarize_chunk(self, chunk: str, topic: str) -> str:
        if self.model:
            prompt = f"Summarize this text for topic '{topic}' in 2-3 sentences:\n{chunk[:2400]}"
            try:
                response = self.model.generate(prompt).text.strip()
                if response:
                    return response
            except Exception:
                pass
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        return " ".join(lines[:3])[:400]

    def _merge_summaries(self, summaries: list[str], topic: str) -> str:
        combined = "\n".join(item for item in summaries if item.strip())
        if not combined:
            return ""
        if self.model and len(summaries) > 1:
            prompt = f"Merge these partial summaries for '{topic}' into one concise summary:\n{combined[:3200]}"
            try:
                response = self.model.generate(prompt).text.strip()
                if response:
                    return response
            except Exception:
                pass
        return combined[:1200]
