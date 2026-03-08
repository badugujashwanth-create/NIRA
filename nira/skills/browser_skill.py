from __future__ import annotations

from nira_agent.automation.permissions import STANDARD
from nira_agent.automation.tool_registry import ToolSpec
from nira_agent.skills.base import register_specs


def register(registry, executors) -> None:
    specs = [
        ToolSpec(
            name="open_url",
            executor=executors.open_url,
            required_args=["url"],
            arg_types={"url": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
    ]
    register_specs(registry, specs)
