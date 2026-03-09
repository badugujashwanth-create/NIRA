from __future__ import annotations

from typing import Any

from nira.tools.base import Tool, ToolResult


class BrowserController(Tool):
    name = "browse_sources"
    description = "Inspect local sources and optionally fetch allowed web content."

    def __init__(self, source_analyzer, web_enabled: bool = False) -> None:
        self.source_analyzer = source_analyzer
        self.web_enabled = web_enabled

    def run(self, args: dict[str, Any], state) -> ToolResult:
        query = str(args.get("query") or args.get("path") or "").strip()
        use_web = bool(args.get("use_web", False)) and self.web_enabled
        source_paths = list(args.get("source_paths", []) or [])
        result = self.source_analyzer.analyze(query=query, use_web=use_web, source_paths=source_paths)
        return ToolResult(result.ok, result.summary, result.data)
