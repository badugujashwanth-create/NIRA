from __future__ import annotations

from plugins.base import PluginResult


class NewsPlugin:
    name = "news"

    def can_handle(self, query: str) -> bool:
        return "news" in query.lower()

    def execute(self, query: str) -> PluginResult:
        return PluginResult(
            plugin=self.name,
            text=f"News plugin received: {query}. Attach a feed provider to return live headlines.",
        )
