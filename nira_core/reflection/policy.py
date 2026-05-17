from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PolicyAdjustment:
    """A safe orchestration policy adjustment."""

    name: str
    value: Any
    reason: str


@dataclass(slots=True)
class AdaptivePolicyState:
    """Current adaptive policy knobs; no unsafe actions are executed here."""

    context_budget_tokens: int | None = None
    route_overrides: dict[str, str] = field(default_factory=dict)
    reranker_weight: float = 1.0
    latency_mode: str = "balanced"
    notes: list[str] = field(default_factory=list)


class ReflectionPolicyEngine:
    """Heuristic policy engine driven by state and telemetry."""

    def __init__(
        self,
        hallucination_threshold: float = 0.45,
        inference_queue_threshold: int = 5,
        retrieval_precision_threshold: float = 0.35,
        ram_high_mb: float = 11_000.0,
    ) -> None:
        self.hallucination_threshold = hallucination_threshold
        self.inference_queue_threshold = inference_queue_threshold
        self.retrieval_precision_threshold = retrieval_precision_threshold
        self.ram_high_mb = ram_high_mb

    def evaluate(self, snapshot: dict[str, Any]) -> list[PolicyAdjustment]:
        """Return safe adaptive policy changes from current state."""

        adjustments: list[PolicyAdjustment] = []
        hallucination = float(snapshot.get("hallucination_score", 0.0))
        if hallucination > self.hallucination_threshold:
            adjustments.append(
                PolicyAdjustment(
                    name="context_budget_tokens",
                    value=320,
                    reason="hallucination_score_high_reduce_prompt_surface",
                )
            )
        queue_depth = snapshot.get("queue_depth", {})
        inference_depth = int(queue_depth.get("inference", 0)) if isinstance(queue_depth, dict) else 0
        if inference_depth > self.inference_queue_threshold:
            adjustments.append(
                PolicyAdjustment(
                    name="route_override",
                    value={"coding": "fast", "deep_reasoning": "fast"},
                    reason="inference_queue_pressure_downgrade_to_fast_model",
                )
            )
            adjustments.append(PolicyAdjustment(name="latency_mode", value="fast", reason="queue_pressure"))
        retrieval_precision = float(snapshot.get("retrieval_precision", 0.0))
        if 0.0 < retrieval_precision < self.retrieval_precision_threshold:
            adjustments.append(
                PolicyAdjustment(
                    name="reranker_weight",
                    value=1.25,
                    reason="retrieval_precision_low_increase_reranker_weight",
                )
            )
        ram_usage = float(snapshot.get("ram_usage_mb", 0.0))
        if ram_usage > self.ram_high_mb:
            adjustments.append(
                PolicyAdjustment(
                    name="route_override",
                    value={"deep_reasoning": "fast"},
                    reason="ram_usage_high_avoid_large_reasoning_model",
                )
            )
            adjustments.append(PolicyAdjustment(name="context_budget_tokens", value=280, reason="ram_pressure"))
        return adjustments
