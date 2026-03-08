from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from nira_agent.automation.models import ToolCall, ToolResult


@dataclass
class Workflow:
    name: str
    permission: str = "standard"
    steps: list[ToolCall] = field(default_factory=list)


@dataclass
class WorkflowParseResult:
    workflows: dict[str, Workflow]
    errors: list[str]


class WorkflowDSLParser:
    """Parses DSL:

    workflow daily_start permission=standard:
      open_app target="notepad.exe"
      open_url url="https://news.ycombinator.com"
    """

    def parse(self, text: str) -> WorkflowParseResult:
        workflows: dict[str, Workflow] = {}
        errors: list[str] = []
        current: Workflow | None = None

        for idx, raw in enumerate(text.splitlines(), start=1):
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.lower().startswith("workflow "):
                wf, err = self._parse_header(stripped)
                if err:
                    errors.append(f"Line {idx}: {err}")
                    current = None
                    continue
                if wf.name in workflows:
                    errors.append(f"Line {idx}: Duplicate workflow '{wf.name}'")
                    current = None
                    continue
                workflows[wf.name] = wf
                current = wf
                continue

            if not raw.startswith((" ", "\t")):
                errors.append(f"Line {idx}: Step must be indented under workflow.")
                continue

            if current is None:
                errors.append(f"Line {idx}: Step found without workflow header.")
                continue

            step, err = self._parse_step(stripped)
            if err:
                errors.append(f"Line {idx}: {err}")
                continue
            current.steps.append(step)

        return WorkflowParseResult(workflows=workflows, errors=errors)

    def _parse_header(self, line: str) -> tuple[Workflow, str | None]:
        if not line.endswith(":"):
            return Workflow(name="invalid"), "Workflow header must end with ':'."
        body = line[:-1].strip()
        tokens = shlex.split(body)
        if len(tokens) < 2:
            return Workflow(name="invalid"), "Workflow name missing."
        name = tokens[1].strip().lower()
        permission = "standard"
        for token in tokens[2:]:
            if token.startswith("permission="):
                permission = token.split("=", 1)[1].strip().lower()
        return Workflow(name=name, permission=permission), None

    def _parse_step(self, line: str) -> tuple[ToolCall, str | None]:
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            return ToolCall("invalid"), str(exc)
        if not tokens:
            return ToolCall("invalid"), "Empty step."
        tool = tokens[0]
        args: dict[str, str] = {}
        for token in tokens[1:]:
            if "=" not in token:
                return ToolCall("invalid"), f"Invalid argument '{token}', expected key=value."
            k, v = token.split("=", 1)
            args[k] = v
        return ToolCall(tool=tool, args=args), None


class WorkflowRunner:
    def __init__(self, parser: WorkflowDSLParser) -> None:
        self.parser = parser
        self.workflows: dict[str, Workflow] = {}

    def load_file(self, path: str) -> ToolResult:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError as exc:
            return ToolResult(False, f"Cannot load workflow file: {exc}")
        parsed = self.parser.parse(text)
        if parsed.errors:
            return ToolResult(False, "; ".join(parsed.errors))
        self.workflows = parsed.workflows
        return ToolResult(True, f"Loaded {len(self.workflows)} workflows.")

    def run(self, name: str, execute_step) -> ToolResult:
        wf = self.workflows.get(name.lower())
        if not wf:
            return ToolResult(False, f"Workflow '{name}' not found.")
        for step in wf.steps:
            step_result = execute_step(step)
            if not step_result.ok:
                return ToolResult(False, f"Workflow '{name}' failed at {step.tool}: {step_result.output}")
        return ToolResult(True, f"Workflow '{name}' completed ({len(wf.steps)} steps).")

