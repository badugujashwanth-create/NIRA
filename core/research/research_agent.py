from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from core.research.content_parser import ContentParser
from core.research.web_search import SearchResult, WebSearchClient


@dataclass(slots=True)
class ResearchFinding:
    title: str
    url: str
    summary: str


@dataclass(slots=True)
class ResearchSummary:
    query: str
    findings: list[ResearchFinding] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchAgent:
    def __init__(self, search_client: WebSearchClient, parser: ContentParser | None = None) -> None:
        self.search_client = search_client
        self.parser = parser or ContentParser()

    async def research(self, query: str) -> ResearchSummary:
        try:
            search_results = await self.search_client.search_async(query)
        except Exception as exc:
            return ResearchSummary(
                query=query,
                findings=[],
                summary=f"Research search failed: {exc}",
                metadata={"sources": 0, "error": str(exc)},
            )
        pages = await asyncio.gather(*(self._fetch_and_parse(result) for result in search_results), return_exceptions=True)

        findings: list[ResearchFinding] = []
        for result, page in zip(search_results, pages):
            if isinstance(page, Exception):
                findings.append(ResearchFinding(title=result.title, url=result.url, summary=f"Source fetch failed: {page}"))
                continue
            findings.append(ResearchFinding(title=result.title, url=result.url, summary=page))

        combined = " ".join(finding.summary for finding in findings if finding.summary)
        summary = self.parser.summarize(combined, max_sentences=4) if combined else "No research findings were collected."
        return ResearchSummary(
            query=query,
            findings=findings,
            summary=summary,
            metadata={"sources": len(findings)},
        )

    async def _fetch_and_parse(self, result: SearchResult) -> str:
        html_content = await self.search_client.fetch_page(result.url)
        text = self.parser.extract_text(html_content)
        return self.parser.summarize(text, max_sentences=3)
