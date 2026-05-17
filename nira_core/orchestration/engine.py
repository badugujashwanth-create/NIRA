from __future__ import annotations

from dataclasses import dataclass, field
import time
import uuid

from nira_core.capabilities import CapabilityRecommendationEngine
from nira_core.compression import ContextDistillationPipeline, DistilledContext
from nira_core.events import Event, EventBus, EventType
from nira_core.inference import InferenceRequest
from nira_core.inference.manager import LocalInferenceManager
from nira_core.memory import MemoryManager
from nira_core.reflection import AdaptiveOrchestrationManager
from nira_core.routing import TaskRouter
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry, sample_resources


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """End-to-end task result."""

    text: str
    task_type: str
    model_alias: str
    context_tokens: int
    metadata: dict[str, object] = field(default_factory=dict)


class CognitiveOrchestrator:
    """Coordinates routing, retrieval, compression, inference, and memory updates."""

    def __init__(
        self,
        router: TaskRouter,
        distillation: ContextDistillationPipeline,
        inference: LocalInferenceManager,
        memory: MemoryManager,
        telemetry: Telemetry,
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
        capabilities: CapabilityRecommendationEngine | None = None,
        reflection: AdaptiveOrchestrationManager | None = None,
    ) -> None:
        self._router = router
        self._distillation = distillation
        self._inference = inference
        self._memory = memory
        self._telemetry = telemetry
        self._state = state
        self._event_bus = event_bus
        self._capabilities = capabilities
        self._reflection = reflection

    async def run(self, task: str, task_type: str | None = None) -> OrchestrationResult:
        """Run one event-driven cognitive task using bounded context and serialized inference."""

        started = time.perf_counter()
        task_id = uuid.uuid4().hex
        resources = sample_resources()
        self._telemetry.gauge("ram_usage_mb", resources.ram_used_mb)
        self._telemetry.gauge("cpu_utilization_percent", resources.cpu_percent)
        if self._state is not None:
            self._state.set_resources(resources.ram_used_mb, resources.cpu_percent)
            self._state.start_task(task_id, task_type or "auto", {"task": task[:160]})
        await self._publish(EventType.TASK_CREATED, {"task_id": task_id, "task_type": task_type or "auto"})
        self._telemetry.emit("orchestration.start", {"task_type": task_type or "auto"})
        await self._publish(EventType.TASK_STARTED, {"task_id": task_id})

        plan_payload: dict[str, object] | None = None
        if self._capabilities is not None:
            plan = self._capabilities.recommend(
                task,
                max_ram_mb=512,
                permissions={"filesystem", "subprocess", "network", "local_network"},
            )
            plan_payload = plan.to_dict()
            self._telemetry.emit(
                "capability.plan",
                {"task_id": task_id, "steps": len(plan.capabilities), "estimated_ram_mb": plan.estimated_ram_mb},
            )
            await self._publish(EventType.CAPABILITY_PLANNED, {"task_id": task_id, "plan": plan_payload})

        if self._reflection is not None:
            self._reflection.optimize()
        route = self._router.route(task, explicit_type=task_type)
        if self._reflection is not None:
            route = self._reflection.adjust_route(route)
        context_budget = self._context_budget_for(route.task_type, route.complexity)
        if self._reflection is not None:
            context_budget = self._reflection.context_budget(context_budget)
        if self._use_fast_path(task, route.task_type, route.complexity):
            distilled = DistilledContext(query=task, context="", context_tokens=0, retrieval_results=[])
            self._telemetry.increment("orchestration_fast_path_total")
            self._telemetry.emit(
                "orchestration.fast_path",
                {"task_id": task_id, "task_type": route.task_type, "reason": "low_complexity"},
            )
        else:
            distilled = await self._distillation.build_context(task, max_final_tokens=context_budget)
        prompt = self._build_prompt(task, distilled.context)
        result = await self._inference.generate(
            InferenceRequest(
                prompt=prompt,
                task_type=route.task_type,
                model_alias=route.model_alias,
            )
        )
        self._memory.remember_task(task, result.text, importance=_importance_for(route.task_type))
        if self._reflection is not None:
            self._reflection.observe_task_outcome(
                retrieval_count=len(distilled.retrieval_results),
                context_tokens=distilled.context_tokens,
                completion_tokens=result.token_accounting.completion_tokens,
            )
            self._reflection.optimize()
        duration_ms = (time.perf_counter() - started) * 1000.0
        if self._state is not None:
            self._state.record_latency("orchestration", duration_ms)
            self._state.finish_task(task_id)
        self._telemetry.emit(
            "orchestration.finish",
            {
                "task_id": task_id,
                "task_type": route.task_type,
                "model_alias": route.model_alias,
                "context_tokens": distilled.context_tokens,
                "tokens_per_sec": result.tokens_per_sec,
                "duration_ms": duration_ms,
                "route_confidence": route.confidence,
                "route_complexity": route.complexity,
                "context_budget_tokens": context_budget,
            },
        )
        await self._publish(
            EventType.TASK_COMPLETED,
            {
                "task_id": task_id,
                "task_type": route.task_type,
                "model_alias": route.model_alias,
                "duration_ms": duration_ms,
            },
        )
        return OrchestrationResult(
            text=result.text,
            task_type=route.task_type,
            model_alias=route.model_alias,
            context_tokens=distilled.context_tokens,
            metadata={
                "retrieval_count": len(distilled.retrieval_results),
                "prompt_tokens": result.token_accounting.prompt_tokens,
                "completion_tokens": result.token_accounting.completion_tokens,
                "task_id": task_id,
                "capability_plan": plan_payload,
                "route_confidence": route.confidence,
                "route_complexity": route.complexity,
                "route_reason": route.reason,
                "estimated_cost": route.estimated_cost,
                "context_budget_tokens": context_budget,
            },
        )

    def _build_prompt(self, task: str, context: str) -> str:
        if context:
            return (
                "You are operating inside NIRA local-first cognitive infrastructure. "
                "Use only the distilled context where relevant. Keep the response task-focused.\n\n"
                f"Distilled context:\n{context}\n\nTask:\n{task}\n\nResult:"
            )
        return (
            "You are operating inside NIRA local-first cognitive infrastructure. "
            "Keep the response task-focused and avoid inventing unavailable context.\n\n"
            f"Task:\n{task}\n\nResult:"
        )

    async def _publish(self, event_type: EventType, payload: dict[str, object]) -> None:
        if self._event_bus is not None:
            await self._event_bus.publish(Event.create(event_type, payload))

    def _context_budget_for(self, task_type: str, complexity: str) -> int:
        if task_type == "classification" and complexity == "low":
            return 160
        if task_type in {"classification", "compression"}:
            return 240
        if task_type in {"research", "retrieval"}:
            return 320
        return 400

    def _use_fast_path(self, task: str, task_type: str, complexity: str) -> bool:
        return task_type == "classification" and complexity == "low" and len(task) <= 160


def _importance_for(task_type: str) -> float:
    if task_type in {"coding", "deep_reasoning"}:
        return 0.8
    if task_type in {"compression", "retrieval"}:
        return 0.45
    return 0.55
