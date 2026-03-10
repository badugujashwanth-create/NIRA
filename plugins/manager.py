from __future__ import annotations

from plugins.base import PluginResult
from plugins.calendar_plugin import CalendarPlugin
from plugins.news_plugin import NewsPlugin
from plugins.weather_plugin import WeatherPlugin


class PluginManager:
    def __init__(self) -> None:
        self.plugins = [WeatherPlugin(), NewsPlugin(), CalendarPlugin()]

    def try_execute(self, query: str) -> PluginResult | None:
        for plugin in self.plugins:
            if plugin.can_handle(query):
                return plugin.execute(query)
        return None
