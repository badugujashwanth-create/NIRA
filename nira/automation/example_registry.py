from __future__ import annotations

from nira_agent.automation.builtins import BuiltinExecutors
from nira_agent.automation.permissions import STANDARD
from nira_agent.automation.tool_registry import ToolRegistry, ToolSpec


def build_example_tool_registry() -> ToolRegistry:
    executors = BuiltinExecutors()
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="open_app",
            executor=executors.open_app,
            required_args=["target"],
            arg_types={"target": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        )
    )
    registry.register(
        ToolSpec(
            name="open_url",
            executor=executors.open_url,
            required_args=["url"],
            arg_types={"url": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        )
    )
    return registry
