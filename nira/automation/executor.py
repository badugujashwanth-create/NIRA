from __future__ import annotations

import logging
from typing import Callable

from nira.automation.models import ToolCall, ToolResult
from nira.automation.permissions import DESTRUCTIVE, PermissionManager
from nira.automation.tool_registry import ToolRegistry
from nira.automation.undo import UndoStack


logger = logging.getLogger(__name__)


ConfirmFn = Callable[[ToolCall], bool]


class ToolExecutionEngine:
    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: PermissionManager,
        undo_stack: UndoStack,
        confirm_fn: ConfirmFn,
    ) -> None:
        self.registry = registry
        self.permission_manager = permission_manager
        self.undo_stack = undo_stack
        self.confirm_fn = confirm_fn
        self.safe_mode_enabled = False
        self.max_calls_per_turn = 1
        self.max_repeated_call = 2

    def execute_tool_calls(self, calls: list[ToolCall]) -> list[ToolResult]:
        if len(calls) > self.max_calls_per_turn:
            return [
                ToolResult(
                    False,
                    f"Tool call limit exceeded ({len(calls)} > {self.max_calls_per_turn}). Only one command is allowed at a time.",
                )
            ]

        results: list[ToolResult] = []
        seen: dict[str, int] = {}
        for call in calls:
            sig = f"{call.tool}:{sorted(call.args.items())}"
            seen[sig] = seen.get(sig, 0) + 1
            if seen[sig] > self.max_repeated_call:
                results.append(
                    ToolResult(False, f"Loop protection triggered for repeated tool call '{call.tool}'.")
                )
                continue
            result = self.execute(call)
            results.append(result)
        return results

    def execute(self, call: ToolCall) -> ToolResult:
        validation = self.registry.validate_call(call)
        if not validation.ok:
            return validation

        spec = self.registry.get(call.tool)
        if not spec:
            return ToolResult(False, f"Tool '{call.tool}' is not in whitelist.")

        if self.safe_mode_enabled and spec.permission.rank > 1:
            return ToolResult(False, f"Safe mode active: blocked tool '{call.tool}'.")

        if not self.permission_manager.require(spec.permission):
            self.enable_safe_mode()
            return ToolResult(False, f"Permission denied for tool '{call.tool}'.")

        if (spec.permission.rank >= DESTRUCTIVE.rank) or spec.safe_confirmation_required:
            try:
                confirmed = self.confirm_fn(call)
            except Exception as exc:
                self.enable_safe_mode()
                logger.exception("Security confirmation error for %s", call.tool)
                return ToolResult(False, f"Security confirmation failed for '{call.tool}': {exc}")
            if not confirmed:
                return ToolResult(False, f"Execution cancelled for '{call.tool}' by safety confirmation.")

        try:
            result, action = spec.executor(call.args)
            if action:
                self.undo_stack.push(action)
            return result
        except Exception as exc:
            if "permission" in str(exc).lower() or "security" in str(exc).lower():
                self.enable_safe_mode()
            logger.exception("Tool execution failed for %s", call.tool)
            return ToolResult(False, f"Tool '{call.tool}' failed: {exc}")

    def enable_safe_mode(self) -> None:
        self.safe_mode_enabled = True
        self.permission_manager.force_safe_mode()
