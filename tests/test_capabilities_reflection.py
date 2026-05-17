from __future__ import annotations

from nira_core.capabilities import Capability, CapabilityGraph, CapabilityRecommendationEngine, CapabilityRegistry
from nira_core.reflection import AdaptiveOrchestrationManager
from nira_core.routing import RouteDecision
from nira_core.state import reset_system_state
from nira_core.telemetry import Telemetry


def test_capability_graph_composes_dependencies() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability(name="retrieval.semantic", description="retrieve", tags=("retrieval",)))
    registry.register(
        Capability(
            name="inference.local_generate",
            description="infer",
            dependencies=("retrieval.semantic",),
            tags=("inference",),
            ram_mb=100,
        )
    )
    graph = CapabilityGraph(registry)
    plan = graph.compose("use memory then infer", [registry.get("inference.local_generate")], ram_limit_mb=200)

    assert [capability.name for capability in plan.capabilities] == ["retrieval.semantic", "inference.local_generate"]


def test_recommendation_engine_respects_goal_terms() -> None:
    registry = CapabilityRegistry()
    registry.register(Capability(name="retrieval.semantic", description="retrieve", tags=("retrieval",)))
    registry.register(Capability(name="filesystem.readwrite", description="files", tags=("filesystem",)))
    engine = CapabilityRecommendationEngine(registry, CapabilityGraph(registry))

    plan = engine.recommend("read project file and retrieve context", permissions={"filesystem"})
    names = [capability.name for capability in plan.capabilities]
    assert "filesystem.readwrite" in names
    assert "retrieval.semantic" in names


def test_reflection_downgrades_route_under_queue_pressure(tmp_path) -> None:
    state = reset_system_state()
    state.set_queue_depth("inference", 8)
    manager = AdaptiveOrchestrationManager(state, Telemetry(tmp_path / "telemetry"))

    adjustments = manager.optimize()
    adjusted = manager.adjust_route(RouteDecision(task_type="coding", model_alias="primary_coding", reason="test"))

    assert adjustments
    assert adjusted.model_alias == "fast"
    assert manager.snapshot()["latency_mode"] == "fast"
