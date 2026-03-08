from __future__ import annotations

import logging
from pathlib import Path

from nira_agent.ai.structured_output import StructuredModelOutput
from nira_agent.automation.builtins import BuiltinExecutors
from nira_agent.automation.executor import ToolExecutionEngine
from nira_agent.automation.models import ToolCall, ToolResult
from nira_agent.automation.permissions import PermissionManager
from nira_agent.automation.skill_loader import SkillAutoLoader
from nira_agent.automation.tool_registry import ToolRegistry
from nira_agent.automation.undo import UndoStack
from nira_agent.automation.workflow_dsl import WorkflowDSLParser, WorkflowRunner


logger = logging.getLogger(__name__)


class AutomationManager:
    def __init__(self, permission_level: str, confirm_fn) -> None:
        self.registry = ToolRegistry()
        self.undo_stack = UndoStack()
        self.permission_manager = PermissionManager(permission_level)
        self.executors = BuiltinExecutors()
        self.dsl_parser = WorkflowDSLParser()
        self.workflow_runner = WorkflowRunner(self.dsl_parser)
        self.executors.set_workflow_runner(self._run_workflow)
        self.skill_loader = SkillAutoLoader()
        self.loaded_skills = self.skill_loader.load(self.registry, self.executors)
        self.engine = ToolExecutionEngine(
            registry=self.registry,
            permission_manager=self.permission_manager,
            undo_stack=self.undo_stack,
            confirm_fn=confirm_fn,
        )

    def load_workflows_if_exists(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(False, f"Workflow file not found: {path}")
        return self.workflow_runner.load_file(str(path))

    def parse_model_tool_calls(self, output: StructuredModelOutput) -> tuple[list[ToolCall], ToolResult]:
        if not output.json_valid:
            return [], ToolResult(False, "Model output is not valid JSON; tool execution blocked.")
        if not output.schema_valid:
            return [], ToolResult(False, f"Model schema validation failed: {'; '.join(output.validation_errors)}")

        rows = output.tool_calls
        calls: list[ToolCall] = []
        for row in rows:
            tool = str(row.get("tool", "")).strip()
            args = row.get("args", {})
            if not tool:
                continue
            if not isinstance(args, dict):
                args = {}
            calls.append(ToolCall(tool=tool, args=args))
        return calls, ToolResult(True, "ok")

    def execute_calls(self, calls: list[ToolCall]) -> list[ToolResult]:
        return self.engine.execute_tool_calls(calls)

    def undo_last(self) -> ToolResult:
        return self.undo_stack.undo_last()

    def tool_feedback_text(self, results: list[ToolResult]) -> str:
        lines = []
        for idx, result in enumerate(results, start=1):
            status = "ok" if result.ok else "error"
            lines.append(f"[{idx}] {status}: {result.output}")
        return "\n".join(lines) if lines else "No tool calls were executed."

    def registry_validation_report(self) -> ToolResult:
        issues = self.registry.validate_registry()
        if issues:
            return ToolResult(False, "; ".join(issues))
        return ToolResult(True, "Tool registry validation passed.")

    def workflow_validation_report(self) -> ToolResult:
        try:
            errors: list[str] = []
            for wf in self.workflow_runner.workflows.values():
                for step in wf.steps:
                    validation = self.registry.validate_call(step)
                    if not validation.ok:
                        errors.append(f"{wf.name}:{step.tool} -> {validation.output}")
            if errors:
                return ToolResult(False, "; ".join(errors))
            return ToolResult(True, "Workflow validation passed.")
        except Exception as exc:
            return ToolResult(False, f"Workflow validation error: {exc}")

    def _run_workflow(self, name: str) -> ToolResult:
        return self.workflow_runner.run(name, self.engine.execute)
