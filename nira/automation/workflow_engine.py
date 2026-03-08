from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from nira.ai.intent_parser import IntentParser
from nira.automation.command_executor import CommandExecutor
from nira.automation.dsl_parser import DSLParser


@dataclass
class WorkflowResult:
    success: bool
    message: str


class WorkflowEngine:
    def __init__(self, executor: CommandExecutor, intent_parser: IntentParser) -> None:
        self.executor = executor
        self.intent_parser = intent_parser
        self.dsl_parser = DSLParser()
        self._modes: dict[str, list[str]] = {}

    def load_script(self, dsl_text: str) -> WorkflowResult:
        parsed = self.dsl_parser.parse(dsl_text)
        if parsed.errors:
            return WorkflowResult(False, "; ".join(parsed.errors))
        self._modes = parsed.modes
        return WorkflowResult(True, f"Loaded {len(self._modes)} mode(s).")

    def load_script_file(self, path: str | Path) -> WorkflowResult:
        script_path = Path(path).expanduser()
        if not script_path.exists():
            return WorkflowResult(False, f"Workflow file not found: {script_path}")
        try:
            return self.load_script(script_path.read_text(encoding="utf-8"))
        except OSError as exc:
            return WorkflowResult(False, f"Failed reading workflow file: {exc}")

    def run_mode(self, mode_name: str) -> WorkflowResult:
        key = mode_name.strip().lower()
        steps = self._modes.get(key)
        if not steps:
            return WorkflowResult(False, f"Mode '{mode_name}' is not loaded.")

        for step in steps:
            intent = self.intent_parser.parse(step)
            if intent.kind != "automation":
                return WorkflowResult(False, f"Step is not automation: {step}")
            result = self.executor.execute_action(intent.action, intent.args)
            if not result.success:
                return WorkflowResult(False, f"Mode '{mode_name}' failed at '{step}': {result.message}")
        return WorkflowResult(True, f"Mode '{mode_name}' completed ({len(steps)} steps).")

    @property
    def modes(self) -> dict[str, list[str]]:
        return dict(self._modes)

