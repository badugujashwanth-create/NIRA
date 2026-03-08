from __future__ import annotations

from nira_agent.automation.permissions import DESTRUCTIVE, READ_ONLY, STANDARD
from nira_agent.automation.tool_registry import ToolSpec
from nira_agent.skills.base import register_specs


def register(registry, executors) -> None:
    specs = [
        ToolSpec(
            name="create_folder",
            executor=executors.create_folder,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
        ToolSpec(
            name="move_file",
            executor=executors.move_file,
            required_args=["src", "dst"],
            arg_types={"src": "str", "dst": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
        ToolSpec(
            name="delete_file",
            executor=executors.delete_file,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=DESTRUCTIVE,
            destructive=True,
            safe_confirmation_required=True,
        ),
        ToolSpec(
            name="read_file",
            executor=executors.read_file,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=READ_ONLY,
        ),
        ToolSpec(
            name="write_file",
            executor=executors.write_file,
            required_args=["path", "content"],
            arg_types={"path": "str", "content": "str"},
            allow_extra_args=False,
            permission=STANDARD,
        ),
        ToolSpec(
            name="list_directory",
            executor=executors.list_directory,
            required_args=["path"],
            arg_types={"path": "str"},
            allow_extra_args=False,
            permission=READ_ONLY,
        ),
    ]
    register_specs(registry, specs)
