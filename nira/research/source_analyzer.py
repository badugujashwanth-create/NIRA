from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from nira.core.path_utils import PathSecurityError, resolve_within_root, validate_public_http_url
from nira.core.text_utils import tokenize_terms
from nira.documents.text_extractor import TextExtractor


@dataclass
class SourceAnalysis:
    ok: bool
    topic: str
    key_concepts: list[str] = field(default_factory=list)
    summary: str = ""
    important_information: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    collected_text: str = ""

    @property
    def data(self) -> dict[str, Any]:
        return self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "topic": self.topic,
            "key_concepts": list(self.key_concepts),
            "summary": self.summary,
            "important_information": list(self.important_information),
            "references": list(self.references),
            "collected_text": self.collected_text,
        }


class SourceAnalyzer:
    def __init__(self, model=None, web_enabled: bool = False, text_extractor: TextExtractor | None = None) -> None:
        self.model = model
        self.web_enabled = web_enabled
        self.text_extractor = text_extractor or TextExtractor()

    def analyze(self, query: str, use_web: bool = False, source_paths: list[str] | None = None) -> SourceAnalysis:
        paths = [Path(path).expanduser() for path in (source_paths or [])]
        local_result = self._collect_local_sources(query, paths)
        references = list(local_result["references"])
        collected_text = local_result["text"]
        if use_web and self.web_enabled and query.startswith(("http://", "https://")):
            url_text, url_ref = self._collect_url(query)
            if url_text:
                collected_text = f"{collected_text}\n\n{url_text}".strip()
                references.append(url_ref)
        if not collected_text.strip():
            return SourceAnalysis(False, topic=query, summary="No local research text collected.")

        concepts = self._extract_concepts(query, collected_text)
        important_information = self._extract_important_information(collected_text)
        summary = self._summarize(query, collected_text, concepts)
        return SourceAnalysis(
            ok=True,
            topic=query,
            key_concepts=concepts,
            summary=summary,
            important_information=important_information,
            references=references,
            collected_text=collected_text,
        )

    def _collect_local_sources(self, query: str, source_paths: list[Path]) -> dict[str, object]:
        roots = source_paths or [Path.cwd()]
        references: list[str] = []
        chunks: list[str] = []
        fallback_candidates: list[tuple[str, str]] = []
        query_terms = set(tokenize_terms(query, min_length=3))
        for root in roots:
            try:
                safe_root = resolve_within_root(Path.cwd(), root)
            except (PathSecurityError, OSError):
                continue
            if safe_root.is_file():
                text = self.text_extractor.extract(safe_root, root=Path.cwd())
                if text.strip():
                    references.append(str(safe_root))
                    chunks.append(text)
                continue
            if not safe_root.exists():
                continue
            for candidate in self.text_extractor.iter_text_candidates(safe_root):
                if len(references) >= 16:
                    break
                text = self.text_extractor.extract(candidate, root=Path.cwd())
                if not text.strip():
                    continue
                if len(fallback_candidates) < 16:
                    fallback_candidates.append((str(candidate), text[:6000]))
                candidate_terms = set(tokenize_terms(candidate.name, min_length=3))
                text_terms = set(tokenize_terms(text, min_length=3))
                if query_terms and not (query_terms & candidate_terms or query_terms & text_terms):
                    continue
                references.append(str(candidate))
                chunks.append(text[:6000])
        if not chunks:
            for reference, text in fallback_candidates[:4]:
                references.append(reference)
                chunks.append(text)
        return {"references": references, "text": "\n\n".join(chunks)}

    def _collect_url(self, url: str) -> tuple[str, str]:
        try:
            safe_url = validate_public_http_url(url)
            response = requests.get(safe_url, timeout=20)
            response.raise_for_status()
            return response.text[:6000], safe_url
        except (ValueError, requests.RequestException):
            return "", url

    def _extract_concepts(self, topic: str, text: str) -> list[str]:
        llm_concepts = self._try_model_concepts(topic, text)
        if llm_concepts:
            return llm_concepts[:8]
        candidates = re.findall(r"\b(?:[A-Z]{2,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
        if not candidates:
            candidates = re.findall(r"\b[a-z]{4,}\b", text.lower())
        blocked = {"none", "path", "any", "false", "true", "self", "class", "return"}
        counts = Counter(item.strip() for item in candidates if item.strip())
        concepts = [item for item, _ in counts.most_common(12) if item.strip().lower() not in blocked]
        return concepts[:8]

    def _extract_important_information(self, text: str) -> list[str]:
        lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
        scored = [line for line in lines if len(line.split()) >= 6]
        return scored[:8]

    def _summarize(self, topic: str, text: str, concepts: list[str]) -> str:
        llm_summary = self._try_model_summary(topic, text, concepts)
        if llm_summary:
            return llm_summary
        important = self._extract_important_information(text)
        if important:
            return " ".join(important[:3])
        return text[:400]

    def _try_model_concepts(self, topic: str, text: str) -> list[str]:
        if not self.model:
            return []
        prompt = (
            "Extract key concepts from this research material as JSON with key `key_concepts`.\n"
            f"Topic: {topic}\n"
            f"Text:\n{text[:3000]}\n"
        )
        try:
            response = self.model.generate(prompt).text.strip()
        except Exception:
            return []
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start == -1 or end == -1:
                return []
            payload = json.loads(response[start : end + 1])
            return [str(item).strip() for item in payload.get("key_concepts", []) if str(item).strip()]
        except json.JSONDecodeError:
            return []

    def _try_model_summary(self, topic: str, text: str, concepts: list[str]) -> str:
        if not self.model:
            return ""
        prompt = (
            "Summarize the research material in 3-5 sentences.\n"
            f"Topic: {topic}\n"
            f"Concepts: {concepts}\n"
            f"Text:\n{text[:3000]}\n"
        )
        try:
            return self.model.generate(prompt).text.strip()
        except Exception:
            return ""
