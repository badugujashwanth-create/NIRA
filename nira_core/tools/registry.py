from __future__ import annotations

import time

from nira_core.events import Event, EventBus, EventType
from nira_core.state import SystemState
from nira_core.tools.base import Tool, ToolResult


class ToolRegistry:
    """Registry that ensures all tools are invoked through a single execution boundary."""

    def __init__(self, state: SystemState | None = None, event_bus: EventBus | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self._state = state
        self._event_bus = event_bus

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    async def run(self, name: str, payload: dict[str, object]) -> ToolResult:
        started = time.perf_counter()
        try:
            tool = self._tools[name]
        except KeyError:
            result = ToolResult(False, error=f"unknown_tool:{name}")
            await self._record(name, result, started)
            return result
        result = await tool.run(payload)
        await self._record(name, result, started)
        return result

    def names(self) -> list[str]:
        return sorted(self._tools)

    async def _record(self, name: str, result: ToolResult, started: float) -> None:
        latency_ms = (time.perf_counter() - started) * 1000.0
        if self._state is not None:
            self._state.record_capability_performance(f"tool.{name}", latency_ms, result.ok)
        if self._event_bus is not None and not result.ok:
            await self._event_bus.publish(
                Event.create(EventType.TOOL_FAILED, {"tool": name, "error": result.error, "latency_ms": latency_ms})
            )
