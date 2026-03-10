from __future__ import annotations

from plugins.base import PluginResult


class CalendarPlugin:
    name = "calendar"

    def can_handle(self, query: str) -> bool:
        return "calendar" in query.lower() or "schedule" in query.lower()

    def execute(self, query: str) -> PluginResult:
        return PluginResult(
            plugin=self.name,
            text=f"Calendar plugin received: {query}. Integrate a calendar backend to create real events.",
        )
