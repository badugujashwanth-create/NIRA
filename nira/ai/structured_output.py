from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredModelOutput:
    message: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    goal_achieved: bool | None = None
    json_valid: bool = False
    schema_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    raw: str = ""


class StructuredOutputParser:
    def parse(self, raw_text: str) -> StructuredModelOutput:
        body = (raw_text or "").strip()
        if not body:
            return StructuredModelOutput(
                message="",
                tool_calls=[],
                confidence=0.0,
                goal_achieved=None,
                json_valid=False,
                schema_valid=False,
                validation_errors=["Empty model output."],
                raw=raw_text,
            )

        payload = self._try_json(body)
        if payload is None:
            return StructuredModelOutput(
                message=body,
                tool_calls=[],
                confidence=0.35,
                goal_achieved=None,
                json_valid=False,
                schema_valid=False,
                validation_errors=["Output is not valid JSON object."],
                raw=raw_text,
            )

        message = str(payload.get("message", "")).strip()
        confidence = self._as_confidence(payload.get("confidence", 0.0))
        tool_calls = payload.get("tool_calls", [])
        goal_achieved = payload.get("goal_achieved", None)
        errors: list[str] = []
        allowed_keys = {"message", "tool_calls", "confidence", "goal_achieved"}
        extra_keys = [k for k in payload.keys() if k not in allowed_keys]
        if extra_keys:
            errors.append(f"Unknown keys in output: {', '.join(sorted(extra_keys))}")

        if not isinstance(tool_calls, list):
            errors.append("'tool_calls' must be an array.")
            tool_calls = []

        normalized_calls: list[dict[str, Any]] = []
        for idx, item in enumerate(tool_calls):
            if not isinstance(item, dict):
                errors.append(f"tool_calls[{idx}] must be an object.")
                continue
            tool = item.get("tool")
            args = item.get("args")
            if not isinstance(tool, str) or not tool.strip():
                errors.append(f"tool_calls[{idx}].tool must be non-empty string.")
                continue
            if not isinstance(args, dict):
                errors.append(f"tool_calls[{idx}].args must be object.")
                continue
            normalized_calls.append({"tool": tool.strip(), "args": args})

        if goal_achieved is not None and not isinstance(goal_achieved, bool):
            errors.append("'goal_achieved' must be boolean when provided.")
            goal_achieved = None

        return StructuredModelOutput(
            message=message,
            tool_calls=normalized_calls,
            confidence=confidence,
            goal_achieved=goal_achieved,
            json_valid=True,
            schema_valid=(len(errors) == 0),
            validation_errors=errors,
            raw=raw_text,
        )

    def _try_json(self, text: str) -> dict[str, Any] | None:
        try:
            if text.startswith("```"):
                lines = text.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                if lines and lines[0].strip().lower() == "json":
                    lines = lines[1:]
                text = "\n".join(lines).strip()
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _as_confidence(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, score))
