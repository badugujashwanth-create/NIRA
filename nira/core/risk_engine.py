from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from nira_agent.automation.models import ToolCall
from nira_agent.automation.permissions import DESTRUCTIVE
from nira_agent.automation.tool_registry import ToolRegistry, ToolSpec
from nira_agent.core.exceptions import RiskViolation, ValidationError


SYSTEM_PATH_HINTS = {
    "c:\\windows",
    "c:\\program files",
    "c:\\program files (x86)",
    "c:\\programdata",
}
PATH_ARG_KEYS = {"path", "src", "dst"}


@dataclass(frozen=True)
class RiskAssessment:
    level: str
    reason: str
    warning_message: str = ""
    requires_confirmation: bool = False
    exact_confirmation_phrase: str = ""
    ambiguous: bool = False
    signals: list[str] = field(default_factory=list)


class RiskClassifier:
    def __init__(self, registry: ToolRegistry, project_root: Path) -> None:
        self.registry = registry
        self.project_root = project_root.resolve()

    def sanitize_and_validate(self, call: ToolCall) -> tuple[ToolCall, ToolSpec]:
        validation = self.registry.validate_call(call)
        if not validation.ok:
            raise ValidationError(validation.output)

        spec = self.registry.get(call.tool)
        if not spec:
            raise ValidationError(f"Tool '{call.tool}' is not in whitelist.")

        sanitized = dict(call.args)
        for key in PATH_ARG_KEYS:
            if key not in sanitized:
                continue
            value = sanitized[key]
            if not isinstance(value, str):
                raise ValidationError(f"Path argument '{key}' must be a string.")
            sanitized[key] = self._sanitize_path(value)

        return ToolCall(tool=call.tool, args=sanitized), spec

    def classify(self, call: ToolCall, spec: ToolSpec | None = None) -> RiskAssessment:
        tool = call.tool.lower().strip()
        spec = spec or self.registry.get(call.tool)
        if spec is None:
            raise ValidationError(f"Cannot classify risk for unknown tool '{call.tool}'.")

        signals: list[str] = []
        if spec.permission.rank >= DESTRUCTIVE.rank:
            signals.append("destructive_permission")
        if tool in {"delete_file", "close_app"}:
            signals.append("state_destroying_action")
        if tool in {"write_file", "move_file", "create_folder"}:
            signals.append("filesystem_mutation")
        if tool in {"open_app"}:
            signals.append("process_creation")
        if self._touches_system_path(call):
            signals.append("system_path")

        ambiguous = not bool(signals)

        if "state_destroying_action" in signals or "system_path" in signals:
            level = "critical" if "system_path" in signals else "high"
        elif "filesystem_mutation" in signals or "process_creation" in signals:
            level = "medium"
        else:
            level = "low"

        warning = ""
        confirmation = False
        exact_phrase = ""
        if level == "medium":
            warning = f"Warning: '{call.tool}' may change local state."
        elif level == "high":
            warning = f"High-risk action detected for '{call.tool}'. Explicit confirmation required."
            confirmation = True
        elif level == "critical":
            warning = (
                f"Critical action detected for '{call.tool}'. Exact confirmation phrase required "
                "before execution."
            )
            confirmation = True
            exact_phrase = f"CONFIRM CRITICAL {call.tool}"

        return RiskAssessment(
            level=level,
            reason=", ".join(signals) if signals else "read_only_or_unknown",
            warning_message=warning,
            requires_confirmation=confirmation,
            exact_confirmation_phrase=exact_phrase,
            ambiguous=ambiguous,
            signals=signals,
        )

    @staticmethod
    def enforce_confirmation(risk: RiskAssessment, confirmed: bool, phrase_ok: bool = True) -> None:
        if not risk.requires_confirmation:
            return
        if not confirmed:
            raise RiskViolation("Execution blocked because confirmation was not granted.")
        if risk.level == "critical" and not phrase_ok:
            raise RiskViolation("Execution blocked because critical confirmation phrase was incorrect.")

    def _touches_system_path(self, call: ToolCall) -> bool:
        for key in PATH_ARG_KEYS:
            value = call.args.get(key)
            if not isinstance(value, str):
                continue
            lowered = value.strip().lower()
            for hint in SYSTEM_PATH_HINTS:
                if lowered.startswith(hint):
                    return True
        return False

    def _sanitize_path(self, raw: str) -> str:
        value = raw.strip().strip('"').strip("'")
        if not value:
            raise ValidationError("Path value cannot be empty.")
        if "\x00" in value:
            raise ValidationError("Path contains null bytes.")
        path = Path(value).expanduser()
        try:
            if not path.is_absolute():
                path = (self.project_root / path).resolve()
            else:
                path = path.resolve()
        except OSError as exc:
            raise ValidationError(f"Invalid path '{value}': {exc}") from exc
        return str(path)


def classify_risk(command: ToolCall) -> RiskAssessment:
    """Centralized fallback risk classification by command only."""
    tool = command.tool.lower().strip()
    if tool in {"delete_file", "close_app"}:
        return RiskAssessment(
            level="high",
            reason="state_destroying_action",
            warning_message=f"High-risk action detected for '{command.tool}'. Explicit confirmation required.",
            requires_confirmation=True,
        )
    if tool in {"write_file", "move_file", "create_folder", "open_app"}:
        return RiskAssessment(
            level="medium",
            reason="state_mutation",
            warning_message=f"Warning: '{command.tool}' may change local state.",
            requires_confirmation=False,
        )
    return RiskAssessment(level="low", reason="read_only")
