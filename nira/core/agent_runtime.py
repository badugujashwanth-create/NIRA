from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from nira.agents import CodingAgent, DocumentAgent, EmotionAgent, PlannerAgent, ResearchAgent, SafetyAgent
from nira.config import NiraConfig
from nira.documents.document_creator import DocumentCreator
from nira.documents.document_editor import DocumentEditorService
from nira.documents.format_converter import FormatConverter
from nira.documents.pdf_processor import PDFProcessor
from nira.documents.text_extractor import TextExtractor
from nira.intelligence.confidence import ConfidenceEngine
from nira.intelligence.intent_analyzer import IntentAnalyzer, IntentResult
from nira.intelligence.planner import Planner
from nira.intelligence.reflection_engine import ReflectionEngine
from nira.memory.error_memory import ErrorMemory
from nira.memory.knowledge_graph import KnowledgeGraph
from nira.memory.research_memory import ResearchMemory
from nira.memory.short_term_memory import ShortTermMemory
from nira.memory.vector_store import VectorStore
from nira.memory.workflow_memory import WorkflowMemory
from nira.models import LocalModel, ModelContextBuilder, ModelManager, ModelRegistry, ModelSelector, RoutedModelClient
from nira.monitoring.anomaly_detector import AnomalyDetector
from nira.monitoring.performance_analyzer import PerformanceAnalyzer
from nira.monitoring.system_metrics import SystemMetrics
from nira.research.report_generator import ReportGenerator
from nira.research.source_analyzer import SourceAnalyzer
from nira.research.summarizer import Summarizer
from nira.research.topic_planner import TopicPlanner
from nira.task_graph.executor import ExecutionSummary, TaskGraphExecutor
from nira.task_graph.planner import TaskGraphPlanner
from nira.tools import ToolRegistry, build_default_registry
from nira.training.interaction_logger import InteractionLogger
from nira.workflows.pattern_detector import PatternDetector
from nira.workflows.workflow_engine import WorkflowEngine
from nira.workflows.workflow_registry import WorkflowRegistry


@dataclass
class AgentState:
    user_input: str = ""
    intent: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    memory_hits: dict[str, Any] = field(default_factory=dict)
    plan: list[dict[str, Any]] = field(default_factory=list)
    current_task: str | None = None
    tool_result: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    risk_level: str = "low"


@dataclass
class RuntimeResponse:
    text: str
    state: AgentState
    plan: list[dict[str, Any]] = field(default_factory=list)
    task_results: list[dict[str, Any]] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)


RuntimeListener = Callable[[dict[str, Any]], None]


class AgentRuntime:
    """Canonical local-first NIRA runtime."""

    def __init__(
        self,
        config: NiraConfig,
        model: LocalModel | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.config = config
        self.model = model
        self.intent_analyzer = IntentAnalyzer()
        self.short_term_memory = ShortTermMemory(max_turns=config.max_short_term_turns)
        self.performance_analyzer = PerformanceAnalyzer(config.database_path)
        self.model_registry = ModelRegistry.from_config(config)
        self.model_selector = ModelSelector(self.model_registry)
        self.model_context_builder = ModelContextBuilder(config.max_context_chars)
        self.model_manager = ModelManager(
            self.model_registry,
            performance_analyzer=self.performance_analyzer,
            max_cached_models=config.max_cached_models,
            idle_ttl_sec=config.model_idle_ttl_sec,
            default_model=model,
        )
        self.planning_model = RoutedModelClient(self.model_manager, self.model_selector, default_task_type="planning", role="planner")
        self.coding_model = RoutedModelClient(self.model_manager, self.model_selector, default_task_type="coding", role="coding")
        self.research_model = RoutedModelClient(self.model_manager, self.model_selector, default_task_type="research", role="research")
        self.document_model = RoutedModelClient(self.model_manager, self.model_selector, default_task_type="document", role="document")
        self.quick_model = RoutedModelClient(self.model_manager, self.model_selector, default_task_type="quick", role="emotion")
        self.embedding_model = RoutedModelClient(
            self.model_manager,
            self.model_selector,
            default_task_type="embedding",
            role="embedding",
            fixed_alias="embedding_model",
        )
        self.vector_store = VectorStore(config.database_path, self.embedding_model, top_k=config.max_vector_hits)
        self.knowledge_graph = KnowledgeGraph(config.database_path)
        self.workflow_memory = WorkflowMemory(config.database_path)
        self.error_memory = ErrorMemory(config.database_path)
        self.research_memory = ResearchMemory(config.database_path)
        self.topic_planner = TopicPlanner(self.research_model)
        self.text_extractor = TextExtractor()
        self.source_analyzer = SourceAnalyzer(model=self.research_model, web_enabled=config.web_research_enabled, text_extractor=self.text_extractor)
        self.summarizer = Summarizer(self.research_model)
        self.report_generator = ReportGenerator(config.research_dir)
        self.document_creator = DocumentCreator(self.document_model, config.documents_dir)
        self.pdf_processor = PDFProcessor()
        self.document_editor = DocumentEditorService(config.documents_dir)
        self.format_converter = FormatConverter(config.documents_dir)
        self.workflow_registry = WorkflowRegistry(config.workflow_store_path)
        self.workflow_registry.ensure_builtin_workflows()
        self.pattern_detector = PatternDetector(threshold=config.workflow_detection_threshold)
        self.workflow_engine = WorkflowEngine(self.pattern_detector, self.workflow_registry, self.workflow_memory)
        self.system_metrics = SystemMetrics()
        self.anomaly_detector = AnomalyDetector()
        self.interaction_logger = InteractionLogger(config.training_dir / "interactions.jsonl")
        self.planner_agent = PlannerAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.research_agent = ResearchAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.coding_agent = CodingAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.document_agent = DocumentAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.safety_agent = SafetyAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.emotion_agent = EmotionAgent(self.model_manager, self.model_selector, self.model_context_builder)
        self.planner = Planner(self.planner_agent)
        self.task_graph_planner = TaskGraphPlanner(self.planner)
        self.reflection_engine = ReflectionEngine(self.quick_model)
        self.confidence_engine = ConfidenceEngine()
        self.tool_registry = tool_registry or build_default_registry(
            model=self.coding_model,
            config=self.config,
            source_analyzer=self.source_analyzer,
            report_generator=self.report_generator,
            document_editor=self.document_editor,
            topic_planner=self.topic_planner,
            summarizer=self.summarizer,
            research_memory=self.research_memory,
            vector_store=self.vector_store,
            knowledge_graph=self.knowledge_graph,
        )
        self.task_executor = TaskGraphExecutor(self.tool_registry, self.reflection_engine)
        self._status_listeners: list[RuntimeListener] = []

    def add_status_listener(self, listener: RuntimeListener) -> None:
        self._status_listeners.append(listener)

    def remove_status_listener(self, listener: RuntimeListener) -> None:
        self._status_listeners = [item for item in self._status_listeners if item is not listener]

    def handle(self, user_input: str) -> RuntimeResponse:
        started = time.perf_counter()
        self._emit_status("input_received", f"Received request: {user_input}", payload={"text": user_input})
        intent = self.intent_analyzer.analyze(user_input)
        self._emit_status("intent_analyzed", f"Detected intent: {intent.kind}", payload={"intent": intent.to_dict()})
        memory_hits = self._collect_memory_hits(user_input, intent)
        context = self._build_context(intent, memory_hits)
        state = AgentState(
            user_input=user_input,
            intent=intent.to_dict(),
            context=context,
            memory_hits=memory_hits,
        )
        self.short_term_memory.add_turn("user", user_input)
        agent_response = self._select_agent(intent).respond(user_input, context)
        guidance = ""
        if agent_response is not None and hasattr(agent_response, "text"):
            guidance = str(agent_response.text or "")
        self._emit_status("planning_started", f"Planning {intent.goal or user_input}...")
        graph = self.task_graph_planner.build_graph(user_input, intent, context, memory_hits, guidance)
        state.plan = [node.to_dict() for node in graph.nodes]
        state.context["progress"] = list(state.plan)
        self._emit_status(
            "plan_ready",
            f"Prepared {len(graph.nodes)} task(s).",
            tasks=state.plan,
            payload={"intent": intent.to_dict()},
        )
        state.risk_level = self.safety_agent.assess_risk(user_input, graph)
        execution = self.task_executor.execute(graph, state, progress_callback=self._forward_progress_update)
        state.plan = [node.to_dict() for node in graph.nodes]
        state.current_task = execution.current_task
        state.context["model_stats"] = self.model_manager.stats()
        if execution.results:
            state.tool_result = execution.results[-1].to_dict()
        state.confidence = self.confidence_engine.score(state, execution)
        reflection = self.reflection_engine.reflect(state, execution, guidance)
        final_text = self.emotion_agent.polish_response(reflection.summary, state.confidence)
        self._emit_status(
            "response_ready",
            "Prepared final response.",
            tasks=state.plan,
            payload={"confidence": state.confidence},
        )
        anomalies = self._finalize_run(user_input, final_text, intent, execution, started)
        for anomaly in anomalies:
            self._emit_status("anomaly", anomaly, tasks=state.plan, payload={"anomaly": anomaly})
        self._emit_status(
            "completed",
            "Request completed.",
            tasks=state.plan,
            payload={"success": execution.success, "response": final_text},
        )
        return RuntimeResponse(
            text=final_text,
            state=state,
            plan=[node.to_dict() for node in graph.nodes],
            task_results=[result.to_dict() for result in execution.results],
            anomalies=anomalies,
        )

    def process(self, user_input: str) -> RuntimeResponse:
        return self.handle(user_input)

    def shutdown(self) -> None:
        self.model_manager.close()

    def _collect_memory_hits(self, user_input: str, intent: IntentResult) -> dict[str, Any]:
        return {
            "short_term": [turn.to_dict() for turn in self.short_term_memory.recent()],
            "vector_store": self.vector_store.search(user_input),
            "knowledge_graph": self.knowledge_graph.lookup_terms(intent.keywords),
            "workflow_memory": self.workflow_memory.search(user_input),
            "error_memory": self.error_memory.search(user_input),
            "research_memory": self.research_memory.search(user_input),
        }

    def _build_context(self, intent: IntentResult, memory_hits: dict[str, Any]) -> dict[str, Any]:
        cwd = Path.cwd()
        manifests = [
            name
            for name in (
                "pyproject.toml",
                "requirements.txt",
                "package.json",
                "README.md",
                "build.gradle",
                "build.gradle.kts",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
            )
            if (cwd / name).exists()
        ]
        errors = memory_hits.get("error_memory", [])
        error_item = errors[0] if errors else {}
        last_error = str(error_item.get("output", "")) if isinstance(error_item, dict) else ""
        previous_conversation = [
            {
                "role": str(item.get("role", "")),
                "text": str(item.get("content", "")),
            }
            for item in memory_hits.get("short_term", [])[-6:]
        ]
        return {
            "cwd": str(cwd),
            "platform": os.name,
            "available_tools": self.tool_registry.list_tools(),
            "manifests": manifests,
            "artifacts_dir": str(self.config.artifacts_dir),
            "intent_kind": intent.kind,
            "active_project": cwd.name,
            "language": self._detect_primary_language(cwd, manifests),
            "last_error": last_error,
            "active_task": "",
            "previous_conversation": previous_conversation,
            "model_registry": self.model_registry.to_mapping(),
            "model_stats": self.model_manager.stats(),
            "workflow_matches": memory_hits.get("workflow_memory", []),
            "retrieved_knowledge": memory_hits.get("research_memory", [])[:3],
            "vector_hits": memory_hits.get("vector_store", [])[:3],
        }

    def _select_agent(self, intent: IntentResult):
        if intent.kind == "research_topic":
            return self.research_agent
        if intent.kind == "document":
            return self.document_agent
        if intent.kind == "coding":
            return self.coding_agent
        return self.planner_agent

    def _finalize_run(
        self,
        user_input: str,
        final_text: str,
        intent: IntentResult,
        execution: ExecutionSummary,
        started: float,
    ) -> list[str]:
        duration_ms = (time.perf_counter() - started) * 1000
        task_trace = execution.trace
        self.short_term_memory.add_turn("assistant", final_text)
        self.vector_store.add_text("conversation", user_input, {"role": "user", "kind": intent.kind})
        self.vector_store.add_text("conversation", final_text, {"role": "assistant", "kind": intent.kind})
        self.workflow_memory.record_trace(task_trace, success=execution.success)
        self.workflow_engine.observe(task_trace, execution.success)
        self.error_memory.record_execution(execution)
        self.knowledge_graph.add_document(user_input, final_text)
        self.performance_analyzer.record("runtime.handle", duration_ms, execution.success)
        anomalies = self.anomaly_detector.inspect(
            self.system_metrics.snapshot(),
            self.performance_analyzer.summary(),
            execution,
        )
        self.interaction_logger.log(
            {
                "input": user_input,
                "response": final_text,
                "intent": intent.to_dict(),
                "trace": task_trace,
                "results": [result.to_dict() for result in execution.results],
                "anomalies": anomalies,
                "duration_ms": duration_ms,
            }
        )
        return anomalies

    def _forward_progress_update(self, event: dict[str, Any]) -> None:
        self._emit_status(
            str(event.get("event", "task_progress")),
            str(event.get("message", "")),
            tasks=event.get("tasks"),
            payload=event.get("payload"),
        )

    def _emit_status(
        self,
        event: str,
        message: str,
        *,
        tasks: list[dict[str, Any]] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self._status_listeners:
            return
        status = {
            "event": event,
            "message": message,
            "tasks": list(tasks or []),
            "payload": dict(payload or {}),
        }
        for listener in list(self._status_listeners):
            try:
                listener(status)
            except Exception:
                continue

    @staticmethod
    def _detect_primary_language(cwd: Path, manifests: list[str]) -> str:
        manifest_set = set(manifests)
        if {"build.gradle", "build.gradle.kts", "pom.xml"} & manifest_set:
            return "Kotlin/Java"
        if "package.json" in manifest_set:
            return "JavaScript/TypeScript"
        if {"pyproject.toml", "requirements.txt"} & manifest_set:
            return "Python"
        if "Cargo.toml" in manifest_set:
            return "Rust"
        if "go.mod" in manifest_set:
            return "Go"
        for extension, language in (
            ("*.kt", "Kotlin"),
            ("*.java", "Java"),
            ("*.py", "Python"),
            ("*.ts", "TypeScript"),
            ("*.js", "JavaScript"),
            ("*.rs", "Rust"),
            ("*.go", "Go"),
        ):
            if any(cwd.glob(extension)):
                return language
        return "Unknown"
