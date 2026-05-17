from __future__ import annotations

from dataclasses import asdict
from typing import Any

from nira_core.events import Event, EventBus, EventType
from nira_core.reflection.policy import AdaptivePolicyState, ReflectionPolicyEngine
from nira_core.routing import RouteDecision
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry


class AdaptiveOrchestrationManager:
    """Applies safe cognitive feedback policies to orchestration choices."""

    def __init__(
        self,
        state: SystemState,
        telemetry: Telemetry,
        event_bus: EventBus | None = None,
        policy_engine: ReflectionPolicyEngine | None = None,
    ) -> None:
        self._state = state
        self._telemetry = telemetry
        self._event_bus = event_bus
        self._policy_engine = policy_engine or ReflectionPolicyEngine()
        self._policy_state = AdaptivePolicyState()

    @property
    def policy_state(self) -> AdaptivePolicyState:
        return self._policy_state

    def optimize(self) -> list[dict[str, Any]]:
        """Evaluate state and update safe policy knobs."""

        adjustments = self._policy_engine.evaluate(self._state.snapshot())
        for adjustment in adjustments:
            if adjustment.name == "context_budget_tokens":
                self._policy_state.context_budget_tokens = int(adjustment.value)
            elif adjustment.name == "route_override":
                self._policy_state.route_overrides.update(dict(adjustment.value))
            elif adjustment.name == "reranker_weight":
                self._policy_state.reranker_weight = float(adjustment.value)
            elif adjustment.name == "latency_mode":
                self._policy_state.latency_mode = str(adjustment.value)
            self._policy_state.notes.append(adjustment.reason)
        if adjustments:
            payload = {"adjustments": [asdict(adjustment) for adjustment in adjustments], "policy": self.snapshot()}
            self._telemetry.increment("reflection_adjustments_total", len(adjustments))
            self._telemetry.emit("reflection.applied", payload)
            if self._event_bus is not None:
                self._event_bus.publish_nowait(Event.create(EventType.REFLECTION_APPLIED, payload))
        return [asdict(adjustment) for adjustment in adjustments]

    def adjust_route(self, decision: RouteDecision) -> RouteDecision:
        """Return an adjusted route decision when current policy says to downgrade."""

        override = self._policy_state.route_overrides.get(decision.task_type)
        if not override or override == decision.model_alias:
            return decision
        adjusted = RouteDecision(
            task_type=decision.task_type,
            model_alias=override,
            reason=f"{decision.reason}; reflection_override={override}",
            confidence=max(0.0, decision.confidence - 0.08),
            complexity=decision.complexity,
            estimated_cost="low",
        )
        self._telemetry.increment("routing_overrides_total")
        self._telemetry.emit(
            "routing.changed",
            {"from": decision.model_alias, "to": adjusted.model_alias, "task_type": decision.task_type},
        )
        if self._event_bus is not None:
            self._event_bus.publish_nowait(
                Event.create(
                    EventType.ROUTING_CHANGED,
                    {"from": decision.model_alias, "to": adjusted.model_alias, "task_type": decision.task_type},
                )
            )
        return adjusted

    def context_budget(self, default_tokens: int) -> int:
        """Return the active final context budget."""

        return min(default_tokens, self._policy_state.context_budget_tokens or default_tokens)

    def observe_task_outcome(self, retrieval_count: int, context_tokens: int, completion_tokens: int) -> None:
        """Update lightweight quality signals from completed work."""

        hallucination_score = 0.0
        if retrieval_count == 0 and completion_tokens > 80:
            hallucination_score = 0.35
        if context_tokens < 20 and completion_tokens > 160:
            hallucination_score = max(hallucination_score, 0.5)
        self._state.record_hallucination_score(hallucination_score)
        self._state.record_routing_quality("last_task", max(0.0, 1.0 - hallucination_score))

    def snapshot(self) -> dict[str, Any]:
        return {
            "context_budget_tokens": self._policy_state.context_budget_tokens,
            "route_overrides": dict(self._policy_state.route_overrides),
            "reranker_weight": self._policy_state.reranker_weight,
            "latency_mode": self._policy_state.latency_mode,
            "notes": self._policy_state.notes[-20:],
        }
