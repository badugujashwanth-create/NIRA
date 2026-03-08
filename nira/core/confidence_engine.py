from __future__ import annotations

import re
from dataclasses import dataclass, field

from nira_agent.ai.structured_output import StructuredModelOutput
from nira_agent.automation.tool_registry import ToolRegistry
from nira_agent.core.context_snapshot import ContextSnapshot
from nira_agent.core.risk_engine import RiskAssessment


@dataclass(frozen=True)
class ConfidenceReport:
    score: float
    reasons: list[str] = field(default_factory=list)
    tool_availability_ok: bool = True
    json_schema_valid: bool = True
    risk_ambiguity: bool = False
    context_mismatch: bool = False
    ambiguous_language: bool = False
    needs_clarification: bool = False


class DecisionConfidenceEngine:
    _AMBIGUOUS_PATTERNS = (
        r"\bmaybe\b",
        r"\bsomething\b",
        r"\bsomewhere\b",
        r"\bwhatever\b",
        r"\bany\b",
        r"\bit\b",
    )

    def __init__(self, threshold: float) -> None:
        self.threshold = max(0.0, min(1.0, threshold))

    def evaluate(
        self,
        user_input: str,
        output: StructuredModelOutput,
        registry: ToolRegistry,
        context_snapshot: ContextSnapshot,
        risk_assessments: list[RiskAssessment],
        historical_success: dict[str, tuple[int, int]],
    ) -> ConfidenceReport:
        reasons: list[str] = []
        score = output.confidence if output.confidence > 0 else 0.55

        json_schema_valid = output.json_valid and output.schema_valid
        if not output.json_valid:
            score -= 0.35
            reasons.append("Model output JSON is invalid.")
        if output.json_valid and not output.schema_valid:
            score -= 0.25
            reasons.append("Model output schema is invalid.")

        tool_availability_ok = True
        for call in output.tool_calls:
            name = str(call.get("tool", "")).strip()
            if not name or registry.get(name) is None:
                tool_availability_ok = False
                score -= 0.25
                reasons.append(f"Tool unavailable: {name or 'unknown'}.")

        risk_ambiguity = any(r.ambiguous for r in risk_assessments)
        if risk_ambiguity:
            score -= 0.12
            reasons.append("Risk ambiguity detected.")

        ambiguous_language = any(re.search(pattern, user_input.lower()) for pattern in self._AMBIGUOUS_PATTERNS)
        if ambiguous_language and len(user_input.split()) < 8:
            score -= 0.18
            reasons.append("Ambiguous request wording.")

        context_mismatch = self._context_mismatch(user_input, context_snapshot)
        if context_mismatch:
            score -= 0.10
            reasons.append("Context mismatch between request and active workspace.")

        if output.tool_calls:
            similar_scores: list[float] = []
            for call in output.tool_calls:
                tool = str(call.get("tool", "")).strip()
                success, failure = historical_success.get(tool, (0, 0))
                total = success + failure
                if total <= 0:
                    continue
                similar_scores.append(success / total)
            if similar_scores:
                hist = sum(similar_scores) / len(similar_scores)
                score += (hist - 0.5) * 0.30
                reasons.append(f"Historical success influence={hist:.2f}.")

        score = max(0.0, min(1.0, score))
        needs_clarification = score < self.threshold
        if needs_clarification:
            reasons.append(f"Confidence below threshold ({score:.2f} < {self.threshold:.2f}).")

        return ConfidenceReport(
            score=score,
            reasons=reasons,
            tool_availability_ok=tool_availability_ok,
            json_schema_valid=json_schema_valid,
            risk_ambiguity=risk_ambiguity,
            context_mismatch=context_mismatch,
            ambiguous_language=ambiguous_language,
            needs_clarification=needs_clarification,
        )

    @staticmethod
    def _context_mismatch(user_input: str, snapshot: ContextSnapshot) -> bool:
        text = user_input.lower()
        project_hint = snapshot.current_project_path.lower().replace("\\", "/")
        mentions_project = any(token in text for token in ("project", "repo", "codebase", "folder"))
        if not mentions_project:
            return False
        return project_hint.split("/")[-1] not in text and "current" not in text
