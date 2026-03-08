from __future__ import annotations

from nira_agent.automation.tool_registry import ToolRegistry, ToolSpec


def register_specs(registry: ToolRegistry, specs: list[ToolSpec]) -> None:
    for spec in specs:
        registry.register(spec)

