from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.parse import quote_plus

from nira_core.events import Event, EventBus
from nira_core.memory import MemoryManager
from nira_core.orchestration.engine import CognitiveOrchestrator
from nira_core.orchestration.learning import CachedWorkflow, WorkflowLearningStore
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry
from nira_core.tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class WorkflowStepResult:
    """Visible progress item for UI and event traces."""

    name: str
    status: str
    details: str = ""
    duration_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class WorkflowResult:
    """Concrete workflow output returned to API and UI."""

    workflow: str
    answer: str
    steps: list[WorkflowStepResult] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "answer": self.answer,
            "steps": [asdict(step) for step in self.steps],
            "sources": list(self.sources),
            "metadata": dict(self.metadata),
        }


class WorkflowService:
    """Usable end-to-end workflows built on the existing cognitive runtime."""

    def __init__(
        self,
        orchestrator: CognitiveOrchestrator,
        memory: MemoryManager,
        tools: ToolRegistry,
        telemetry: Telemetry,
        event_bus: EventBus,
        state: SystemState,
        learning: WorkflowLearningStore | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._memory = memory
        self._tools = tools
        self._telemetry = telemetry
        self._event_bus = event_bus
        self._state = state
        self._learning = learning

    async def run_coding(self, question: str) -> WorkflowResult:
        """Coding assistant workflow with memory recall and bounded inference."""

        started = time.perf_counter()
        cached = self._cached("coding", question)
        if cached is not None:
            return await self._return_cached(cached, started)
        await self._publish("workflow.started", {"workflow": "coding", "goal": question})
        steps = [WorkflowStepResult("memory_recall", "completed", "Loaded recent and semantic context.")]
        result = await self._orchestrator.run(question, task_type="coding")
        route_confidence = float(result.metadata.get("route_confidence", 0.0))
        details = f"Model: {result.model_alias}"
        if route_confidence:
            details = f"{details}, confidence {route_confidence:.2f}"
        steps.append(WorkflowStepResult("coding_inference", "completed", details))
        self._memory.remember_task(f"Coding workflow: {question}", result.text, importance=0.75)
        duration_ms = _elapsed_ms(started)
        success_score = _score_workflow("coding", result.text, duration_ms, sources=0)
        metadata = {
            "model_alias": result.model_alias,
            "context_tokens": result.context_tokens,
            "duration_ms": duration_ms,
            "success_score": success_score,
            "route_confidence": route_confidence,
            "cache_hit": False,
        }
        await self._publish("workflow.completed", {"workflow": "coding", "duration_ms": duration_ms})
        workflow_result = WorkflowResult(
            workflow="coding",
            answer=result.text,
            steps=steps,
            metadata=metadata,
        )
        self._record("coding", question, workflow_result, duration_ms, success_score, route_confidence)
        return workflow_result

    async def run_research(self, question: str, seed_sources: list[dict[str, str]] | None = None) -> WorkflowResult:
        """Browser research workflow with search, extraction, synthesis, and memory update."""

        started = time.perf_counter()
        if not seed_sources:
            cached = self._cached("browser_research", question)
            if cached is not None:
                return await self._return_cached(cached, started)
        await self._publish("workflow.started", {"workflow": "browser_research", "goal": question})
        steps: list[WorkflowStepResult] = []
        sources = seed_sources or await self._search_web(question)
        steps.append(WorkflowStepResult("web_search", "completed", f"{len(sources)} candidate sources."))
        extracts = await self._extract_sources(sources[:3])
        steps.append(WorkflowStepResult("source_extraction", "completed", f"{len(extracts)} source extracts."))
        source_context = "\n\n".join(
            f"Source: {item['title']}\nURL: {item['url']}\nContent: {item['content']}" for item in extracts
        )
        prompt = (
            f"Research question: {question}\n\n"
            f"Retrieved sources:\n{source_context or 'No live sources available; use existing memory and say what failed.'}\n\n"
            "Synthesize concise findings, include source URLs when available, and note uncertainty."
        )
        result = await self._orchestrator.run(prompt, task_type="research")
        self._memory.remember_task(f"Research workflow: {question}", result.text, importance=0.7)
        duration_ms = _elapsed_ms(started)
        route_confidence = float(result.metadata.get("route_confidence", 0.0))
        details = f"Model: {result.model_alias}"
        if route_confidence:
            details = f"{details}, confidence {route_confidence:.2f}"
        steps.append(WorkflowStepResult("synthesis", "completed", details))
        success_score = _score_workflow("browser_research", result.text, duration_ms, sources=len(extracts))
        metadata = {
            "model_alias": result.model_alias,
            "context_tokens": result.context_tokens,
            "duration_ms": duration_ms,
            "success_score": success_score,
            "route_confidence": route_confidence,
            "cache_hit": False,
        }
        await self._publish("workflow.completed", {"workflow": "browser_research", "duration_ms": duration_ms})
        workflow_result = WorkflowResult(
            workflow="browser_research",
            answer=result.text,
            steps=steps,
            sources=[{"title": item.get("title", ""), "url": item.get("url", "")} for item in extracts],
            metadata=metadata,
        )
        self._record("browser_research", question, workflow_result, duration_ms, success_score, route_confidence)
        return workflow_result

    async def run_planner(self, goal: str) -> WorkflowResult:
        """Multi-step planner workflow that visibly decomposes and synthesizes a goal."""

        started = time.perf_counter()
        cached = self._cached("planner", goal)
        if cached is not None:
            return await self._return_cached(cached, started)
        await self._publish("workflow.started", {"workflow": "planner", "goal": goal})
        plan = self._decompose(goal)
        steps = [WorkflowStepResult("planning", "completed", f"{len(plan)} steps generated.")]
        partials: list[str] = []
        for index, item in enumerate(plan, start=1):
            result = await self._orchestrator.run(f"Planner step {index}/{len(plan)}: {item}", task_type="classification")
            partials.append(f"{index}. {item}: {result.text}")
            steps.append(WorkflowStepResult(f"step_{index}", "completed", item))
        synthesis = await self._orchestrator.run(
            f"Goal: {goal}\n\nStep results:\n" + "\n".join(partials) + "\n\nSynthesize final execution guidance.",
            task_type="deep_reasoning",
        )
        self._memory.remember_task(f"Planner workflow: {goal}", synthesis.text, importance=0.8)
        duration_ms = _elapsed_ms(started)
        route_confidence = float(synthesis.metadata.get("route_confidence", 0.0))
        success_score = _score_workflow("planner", synthesis.text, duration_ms, sources=0)
        metadata = {
            "model_alias": synthesis.model_alias,
            "context_tokens": synthesis.context_tokens,
            "duration_ms": duration_ms,
            "success_score": success_score,
            "route_confidence": route_confidence,
            "cache_hit": False,
        }
        steps.append(WorkflowStepResult("reflection", "completed", "Updated quality signals and memory."))
        await self._publish("workflow.completed", {"workflow": "planner", "duration_ms": duration_ms})
        workflow_result = WorkflowResult(
            workflow="planner",
            answer=synthesis.text,
            steps=steps,
            metadata=metadata,
        )
        self._record("planner", goal, workflow_result, duration_ms, success_score, route_confidence)
        return workflow_result

    async def _search_web(self, query: str) -> list[dict[str, str]]:
        try:
            import httpx

            url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.get(url, headers={"User-Agent": "NIRAmini/1.0"})
            response.raise_for_status()
            return _parse_duckduckgo(response.text)
        except Exception as exc:
            self._telemetry.emit("workflow.research_search_failed", {"error": str(exc)})
            return []

    async def _extract_sources(self, sources: list[dict[str, str]]) -> list[dict[str, str]]:
        extracts: list[dict[str, str]] = []
        for source in sources:
            url = source.get("url", "")
            content = source.get("snippet", "")
            if url.startswith(("http://", "https://")):
                result = await self._tools.run("browser", {"url": url, "selector": "body"})
                if result.ok and result.output:
                    content = result.output[:3000]
            extracts.append({"title": source.get("title", url), "url": url, "content": content})
        return extracts

    def _decompose(self, goal: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"\band\b|,|;", goal) if part.strip()]
        if len(parts) < 2:
            parts = [
                f"Clarify the desired outcome for: {goal}",
                "Retrieve relevant memory and constraints.",
                "Choose safe tools and execution route.",
                "Synthesize final result and record memory.",
            ]
        return parts[:5]

    async def _publish(self, event_type: str, payload: dict[str, object]) -> None:
        await self._event_bus.publish(Event.create(event_type, payload))

    def _cached(self, workflow: str, goal: str) -> CachedWorkflow | None:
        if self._learning is None:
            return None
        cached = self._learning.get_cached(workflow, goal)
        if cached is not None:
            self._telemetry.increment("workflow_cache_hits_total")
            self._telemetry.emit(
                "workflow.cache_hit",
                {"workflow": workflow, "age_seconds": round(cached.age_seconds, 2), "success_score": cached.success_score},
            )
        return cached

    async def _return_cached(self, cached: CachedWorkflow, started: float) -> WorkflowResult:
        duration_ms = _elapsed_ms(started)
        await self._publish(
            "workflow.completed",
            {"workflow": cached.workflow, "duration_ms": duration_ms, "cache_hit": True},
        )
        metadata = dict(cached.metadata)
        metadata.update(
            {
                "cache_hit": True,
                "cache_age_seconds": round(cached.age_seconds, 2),
                "duration_ms": duration_ms,
                "success_score": cached.success_score,
            }
        )
        steps = [WorkflowStepResult("workflow_cache", "completed", "Reused a high-confidence recent workflow result.")]
        steps.extend(
            WorkflowStepResult(
                name=str(item.get("name", "step")),
                status=str(item.get("status", "completed")),
                details=str(item.get("details", "")),
                duration_ms=float(item.get("duration_ms", 0.0) or 0.0),
            )
            for item in cached.steps[:6]
        )
        return WorkflowResult(
            workflow=cached.workflow,
            answer=cached.answer,
            steps=steps,
            sources=[dict(item) for item in cached.sources],
            metadata=metadata,
        )

    def _record(
        self,
        workflow: str,
        goal: str,
        result: WorkflowResult,
        duration_ms: float,
        success_score: float,
        route_confidence: float,
    ) -> None:
        self._telemetry.gauge(f"workflow_{workflow}_success_score", success_score)
        self._telemetry.observe(f"workflow_{workflow}_latency_seconds", duration_ms / 1000.0)
        self._telemetry.emit(
            "workflow.learning_recorded",
            {"workflow": workflow, "success_score": success_score, "route_confidence": route_confidence},
        )
        if self._learning is not None:
            self._learning.record(workflow, goal, result.to_dict(), duration_ms, success_score, route_confidence)


def _parse_duckduckgo(html: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    blocks = re.findall(r'<a rel="nofollow" class="result__a" href="(?P<url>.*?)".*?>(?P<title>.*?)</a>', html, re.S)
    snippets = re.findall(r'<a class="result__snippet".*?>(?P<snippet>.*?)</a>', html, re.S)
    for index, (url, title) in enumerate(blocks[:5]):
        snippet = snippets[index] if index < len(snippets) else ""
        items.append(
            {
                "title": _clean_html(title),
                "url": _clean_html(url),
                "snippet": _clean_html(snippet),
            }
        )
    return items


def _clean_html(value: str) -> str:
    value = re.sub(r"<.*?>", "", value)
    return value.replace("&amp;", "&").replace("&quot;", '"').replace("&#x27;", "'").strip()


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def _score_workflow(workflow: str, answer: str, duration_ms: float, sources: int) -> float:
    score = 0.35 if answer.strip() else 0.0
    if len(answer.strip()) >= 40:
        score += 0.25
    if "unavailable" not in answer.lower() and "failed" not in answer.lower():
        score += 0.2
    if workflow == "browser_research":
        score += 0.15 if sources else -0.1
    else:
        score += 0.1
    if duration_ms < 20_000:
        score += 0.05
    elif duration_ms > 90_000:
        score -= 0.1
    return max(0.0, min(1.0, score))
