from __future__ import annotations

from nira.automation.permissions import READ_ONLY, STANDARD
from nira.automation.tool_registry import ToolSpec
from nira.skills.base import register_specs


def register(registry, executors) -> None:
    specs = [
        ToolSpec(
            name="take_screenshot",
            executor=executors.take_screenshot,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
        ToolSpec(
            name="ocr_image",
            executor=executors.ocr_image,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=READ_ONLY,
        ),
    ]
    register_specs(registry, specs)
