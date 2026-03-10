from __future__ import annotations

from plugins.base import PluginResult


class WeatherPlugin:
    name = "weather"

    def can_handle(self, query: str) -> bool:
        return "weather" in query.lower()

    def execute(self, query: str) -> PluginResult:
        return PluginResult(
            plugin=self.name,
            text=f"Weather plugin received: {query}. Connect a live weather API to return forecasts.",
        )
