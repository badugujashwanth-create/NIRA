from __future__ import annotations

from nira.automation.permissions import DESTRUCTIVE, STANDARD
from nira.automation.tool_registry import ToolSpec
from nira.skills.base import register_specs


def register(registry, executors) -> None:
    specs = [
        ToolSpec(
            name="open_app",
            executor=executors.open_app,
            required_args=["target"],
            arg_types={"target": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
        ToolSpec(
            name="close_app",
            executor=executors.close_app,
            required_args=["process_name"],
            arg_types={"process_name": "str"},
            allow_extra_args=False,
            permission=DESTRUCTIVE,
            destructive=True,
            safe_confirmation_required=True,
        ),
    ]
    register_specs(registry, specs)
