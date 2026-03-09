from __future__ import annotations

from nira.automation.permissions import STANDARD
from nira.automation.tool_registry import ToolSpec
from nira.skills.base import register_specs


def register(registry, executors) -> None:
    specs = [
        ToolSpec(
            name="run_workflow",
            executor=executors.run_workflow,
            required_args=["name"],
            arg_types={"name": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
    ]
    register_specs(registry, specs)
