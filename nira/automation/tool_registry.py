from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from nira.automation.models import ExecutedAction, ToolCall, ToolResult
from nira.automation.permissions import PermissionLevel, READ_ONLY


ToolExecutor = Callable[[dict[str, Any]], tuple[ToolResult, ExecutedAction | None]]


TYPE_MAP = {
    "str": str,
    "int": int,
    "float": (int, float),
    "bool": bool,
    "dict": dict,
    "list": list,
}


@dataclass
class ToolSpec:
    name: str
    executor: ToolExecutor
    required_args: list[str] = field(default_factory=list)
    arg_types: dict[str, str] = field(default_factory=dict)
    allow_extra_args: bool = True
    permission: PermissionLevel = READ_ONLY
    destructive: bool = False
    safe_confirmation_required: bool = False


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._lock = threading.Lock()

    def register(self, spec: ToolSpec) -> None:
        with self._lock:
            self._tools[spec.name] = spec

    def list_tools(self) -> list[str]:
        with self._lock:
            return sorted(self._tools.keys())

    def get(self, name: str) -> ToolSpec | None:
        with self._lock:
            return self._tools.get(name)

    def validate_call(self, call: ToolCall) -> ToolResult:
        if not isinstance(call.tool, str) or not call.tool.strip():
            return ToolResult(False, "Tool name must be a non-empty string.")
        if not isinstance(call.args, dict):
            return ToolResult(False, f"Tool args for '{call.tool}' must be an object.")

        spec = self.get(call.tool)
        if not spec:
            return ToolResult(False, f"Tool '{call.tool}' is not in whitelist.")
        missing = [arg for arg in spec.required_args if arg not in call.args]
        if missing:
            return ToolResult(False, f"Missing required args for '{call.tool}': {', '.join(missing)}")

        if not spec.allow_extra_args:
            allowed = set(spec.required_args) | set(spec.arg_types.keys())
            extras = [key for key in call.args if key not in allowed]
            if extras:
                return ToolResult(False, f"Unexpected args for '{call.tool}': {', '.join(extras)}")

        for arg_name, arg_type in spec.arg_types.items():
            if arg_name not in call.args:
                continue
            expected = TYPE_MAP.get(arg_type)
            if expected is None:
                return ToolResult(False, f"Tool '{call.tool}' has invalid schema type: {arg_type}")
            if not isinstance(call.args[arg_name], expected):
                return ToolResult(
                    False,
                    f"Argument '{arg_name}' for '{call.tool}' must be {arg_type}, got {type(call.args[arg_name]).__name__}.",
                )
        return ToolResult(True, "ok")

    def validate_registry(self) -> list[str]:
        issues: list[str] = []
        with self._lock:
            for name, spec in self._tools.items():
                if not name.strip():
                    issues.append("Tool with empty name is registered.")
                if not callable(spec.executor):
                    issues.append(f"Tool '{name}' has non-callable executor.")
                for arg, t in spec.arg_types.items():
                    if t not in TYPE_MAP:
                        issues.append(f"Tool '{name}' has unsupported arg type '{t}' for '{arg}'.")
        return issues
