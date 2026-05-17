from __future__ import annotations

from dataclasses import dataclass

from nira_core.capabilities import Capability, CapabilityGraph, CapabilityRecommendationEngine, CapabilityRegistry
from nira_core.compression import ContextBudgeter, ContextDistillationPipeline, SemanticCompressor
from nira_core.config import NiraConfig, load_config
from nira_core.events import EventBus
from nira_core.inference import LocalInferenceManager
from nira_core.memory import MemoryManager
from nira_core.orchestration import CognitiveOrchestrator, WorkflowLearningStore, WorkflowService
from nira_core.reflection import AdaptiveOrchestrationManager
from nira_core.retrieval import BGEReranker, RetrievalPipeline
from nira_core.routing import TaskRouter
from nira_core.sandbox import PermissionPolicy, SubprocessSandbox
from nira_core.state import SystemState, reset_system_state
from nira_core.telemetry import Telemetry
from nira_core.tools.browser import BrowserTool
from nira_core.tools.filesystem import FilesystemTool
from nira_core.tools.local_api import LocalAPITool
from nira_core.tools.registry import ToolRegistry
from nira_core.tools.retrieval import RetrievalTool
from nira_core.tools.shell import ShellTool
from nira_core.workers import WorkerRuntime, build_worker_runtime


@dataclass(slots=True)
class NiraRuntime:
    """Concrete runtime object graph for the local-first stack."""

    config: NiraConfig
    telemetry: Telemetry
    memory: MemoryManager
    inference: LocalInferenceManager
    orchestrator: CognitiveOrchestrator
    tools: ToolRegistry
    workers: WorkerRuntime
    state: SystemState
    event_bus: EventBus
    capabilities: CapabilityRegistry
    capability_recommendations: CapabilityRecommendationEngine
    reflection: AdaptiveOrchestrationManager
    workflows: WorkflowService
    workflow_learning: WorkflowLearningStore


def build_runtime(config_path: str | None = None) -> NiraRuntime:
    """Build all layers with explicit dependencies."""

    config = load_config(config_path)
    state = reset_system_state()
    telemetry = Telemetry(config.data_dir / "telemetry")
    telemetry.register_state(state)
    event_bus = EventBus(config.data_dir / "events", telemetry)
    workflow_learning = WorkflowLearningStore(config.data_dir / "workflow_learning.sqlite3")
    memory = MemoryManager(config, telemetry, event_bus=event_bus)
    inference = LocalInferenceManager(config, telemetry, state=state, event_bus=event_bus)
    router = TaskRouter(config, telemetry)
    retrieval = RetrievalPipeline(memory, BGEReranker(), telemetry, state=state, event_bus=event_bus)
    compressor = SemanticCompressor(
        inference,
        telemetry,
        model_alias=config.routing.get("compression", "compression"),
        state=state,
        event_bus=event_bus,
    )
    budgeter = ContextBudgeter(config.runtime.max_final_context_tokens)
    distillation = ContextDistillationPipeline(retrieval, compressor, budgeter, telemetry)
    capability_registry = _build_capabilities(config)
    capability_recommendations = CapabilityRecommendationEngine(capability_registry, CapabilityGraph(capability_registry))
    reflection = AdaptiveOrchestrationManager(state, telemetry, event_bus)
    orchestrator = CognitiveOrchestrator(
        router,
        distillation,
        inference,
        memory,
        telemetry,
        state=state,
        event_bus=event_bus,
        capabilities=capability_recommendations,
        reflection=reflection,
    )
    permissions = PermissionPolicy(config.tools)
    sandbox = SubprocessSandbox(config.tools)
    tools = ToolRegistry(state, event_bus)
    tools.register(FilesystemTool(permissions, config.tools.workspace_root))
    tools.register(ShellTool(permissions, sandbox, config.tools.workspace_root))
    tools.register(BrowserTool())
    tools.register(RetrievalTool(retrieval))
    tools.register(LocalAPITool())
    capability_registry.discover_tools(tools.names())
    workers = build_worker_runtime(config, telemetry, state, event_bus)
    workflows = WorkflowService(orchestrator, memory, tools, telemetry, event_bus, state, learning=workflow_learning)
    return NiraRuntime(
        config=config,
        telemetry=telemetry,
        memory=memory,
        inference=inference,
        orchestrator=orchestrator,
        tools=tools,
        workers=workers,
        state=state,
        event_bus=event_bus,
        capabilities=capability_registry,
        capability_recommendations=capability_recommendations,
        reflection=reflection,
        workflows=workflows,
        workflow_learning=workflow_learning,
    )


def _build_capabilities(config: NiraConfig) -> CapabilityRegistry:
    registry = CapabilityRegistry()
    registry.register(
        Capability(
            name="retrieval.context_distillation",
            description="Retrieve, rerank, compress, and synthesize bounded task context.",
            latency_ms=600,
            ram_mb=300,
            compatible_models=("fast", "compression"),
            execution_type="async",
            dependencies=("retrieval.semantic",),
            tags=("retrieval", "compression", "context"),
        )
    )
    registry.register(
        Capability(
            name="inference.local_generate",
            description="Run serialized CPU-only local inference through the selected backend.",
            latency_ms=5000,
            ram_mb=4500,
            compatible_models=tuple(config.models),
            execution_type="serialized",
            dependencies=("retrieval.context_distillation",),
            tags=("inference", "model"),
        )
    )
    registry.register(
        Capability(
            name="memory.update",
            description="Persist task traces into bounded episodic and semantic memory.",
            latency_ms=120,
            ram_mb=80,
            execution_type="async",
            tags=("memory",),
        )
    )
    return registry
