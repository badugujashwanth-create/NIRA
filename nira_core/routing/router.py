from __future__ import annotations

from dataclasses import dataclass

from nira_core.config import NiraConfig
from nira_core.telemetry import Telemetry


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """A transparent routing decision for observability."""

    task_type: str
    model_alias: str
    reason: str
    confidence: float = 0.7
    complexity: str = "normal"
    estimated_cost: str = "low"


class TaskRouter:
    """Heuristic router with configuration override points."""

    def __init__(self, config: NiraConfig, telemetry: Telemetry) -> None:
        self._config = config
        self._telemetry = telemetry

    def route(self, task: str, explicit_type: str | None = None) -> RouteDecision:
        """Route a task to a configured model alias."""

        task_type = explicit_type or self._classify(task)
        alias = self._config.routing.get(task_type, self._config.routing.get("general", "fast"))
        complexity = self._complexity(task, task_type)
        confidence = self._confidence(task, task_type, explicit_type is not None)
        estimated_cost = self._estimated_cost(alias)
        reason = f"task_type={task_type}; complexity={complexity}; confidence={confidence:.2f}"
        decision = RouteDecision(
            task_type=task_type,
            model_alias=alias,
            reason=reason,
            confidence=confidence,
            complexity=complexity,
            estimated_cost=estimated_cost,
        )
        self._telemetry.emit(
            "routing.decision",
            {
                "task_type": decision.task_type,
                "model_alias": decision.model_alias,
                "reason": decision.reason,
                "confidence": decision.confidence,
                "complexity": decision.complexity,
                "estimated_cost": decision.estimated_cost,
            },
        )
        self._telemetry.gauge("routing_confidence", decision.confidence)
        self._telemetry.increment("routing_decisions_total")
        return decision

    def _classify(self, task: str) -> str:
        text = task.lower()
        coding_markers = (
            "code",
            "test",
            "debug",
            "refactor",
            "function",
            "class",
            "api",
            "python",
            "typescript",
            "sql",
        )
        reasoning_markers = ("prove", "derive", "architecture", "multi-step", "deep reasoning", "tradeoff")
        compression_markers = ("summarize", "compress", "distill", "extract")
        if any(marker in text for marker in coding_markers):
            return "coding"
        if any(marker in text for marker in compression_markers):
            return "compression"
        if any(marker in text for marker in reasoning_markers):
            return "deep_reasoning"
        if len(text.split()) <= 16:
            return "classification"
        return "general"

    def _complexity(self, task: str, task_type: str) -> str:
        words = len(task.split())
        if task_type in {"deep_reasoning", "coding"} or words > 80:
            return "high"
        if task_type in {"classification", "compression"} and words <= 24:
            return "low"
        return "normal"

    def _confidence(self, task: str, task_type: str, explicit: bool) -> float:
        if explicit:
            return 0.93
        words = len(task.split())
        if task_type == "classification" and words <= 16:
            return 0.82
        if task_type in {"coding", "compression", "deep_reasoning"}:
            return 0.78
        return 0.64

    def _estimated_cost(self, alias: str) -> str:
        try:
            spec = self._config.model_for_alias(alias)
        except KeyError:
            return "unknown"
        if spec.heavy:
            return "heavy"
        if spec.num_predict > 220:
            return "medium"
        return "low"
