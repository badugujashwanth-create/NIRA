from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from functools import lru_cache

import requests


RESULT_PATTERN = re.compile(r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', re.IGNORECASE)
TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class WebSearchClient:
    def __init__(self, *, max_results: int = 5, timeout_sec: int = 10) -> None:
        self.max_results = max(1, max_results)
        self.timeout_sec = timeout_sec

    async def search_async(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        return await asyncio.to_thread(self.search, query, max_results)

    @lru_cache(maxsize=64)
    def search(self, query: str, max_results: int | None = None) -> list[SearchResult]:
        limit = max_results or self.max_results
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "NIRA/3.0"},
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        results: list[SearchResult] = []
        for match in RESULT_PATTERN.finditer(response.text):
            title = html.unescape(TAG_PATTERN.sub("", match.group("title"))).strip()
            url = html.unescape(match.group("url")).strip()
            if not title or not url:
                continue
            results.append(SearchResult(title=title, url=url))
            if len(results) >= limit:
                break
        return results

    async def fetch_page(self, url: str) -> str:
        return await asyncio.to_thread(self._fetch_page_sync, url)

    def _fetch_page_sync(self, url: str) -> str:
        response = requests.get(url, headers={"User-Agent": "NIRA/3.0"}, timeout=self.timeout_sec)
        response.raise_for_status()
        return response.text
