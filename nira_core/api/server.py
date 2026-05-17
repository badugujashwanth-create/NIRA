from __future__ import annotations

import asyncio
import json
import tempfile
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Request, Response, WebSocket
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from nira_core.api.schemas import (
    AgentRunRequest,
    CapabilityRecommendRequest,
    ChatRequest,
    MemoryPinRequest,
    MemorySearchRequest,
    ToolRunRequest,
    WorkflowRunRequest,
)
from nira_core.bootstrap import NiraRuntime, build_runtime
from nira_core.telemetry import sample_resources
from nira_core.voice import FasterWhisperTranscriber


def create_app(runtime: NiraRuntime | None = None, config_path: str | None = None) -> FastAPI:
    """Create the FastAPI server with REST and websocket endpoints."""

    runtime_obj = runtime or build_runtime(config_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime_obj
        await app.state.runtime.workers.start()
        try:
            yield
        finally:
            await app.state.runtime.workers.stop()
            await app.state.runtime.event_bus.drain()

    app = FastAPI(title="NIRA Local-First Cognitive Infrastructure", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime_obj
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def root() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/ui")
    async def ui() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    @app.get("/health")
    async def health() -> dict[str, object]:
        resources = sample_resources()
        return {
            "ok": True,
            "cpu_only": app.state.runtime.config.runtime.cpu_only,
            "ram_limit_mb": app.state.runtime.config.runtime.ram_limit_mb,
            "ram_used_mb": resources.ram_used_mb,
        }

    @app.get("/models")
    async def models() -> dict[str, object]:
        return {
            "models": app.state.runtime.inference.models(),
            "current_heavy_model": app.state.runtime.inference.current_heavy_alias,
        }

    @app.post("/chat")
    async def chat(request: ChatRequest) -> dict[str, object]:
        result = await app.state.runtime.workflows.run_coding(request.message) if request.task_type == "coding" else await app.state.runtime.orchestrator.run(request.message, task_type=request.task_type)
        return result.to_dict() if hasattr(result, "to_dict") else asdict(result)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest) -> StreamingResponse:
        async def events():
            yield _sse("status", {"message": "accepted"})
            yield _sse("status", {"message": "orchestrating"})
            result = await app.state.runtime.orchestrator.run(request.message, task_type=request.task_type)
            yield _sse("answer", asdict(result))
            yield _sse("done", {"ok": True})

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/agent/run")
    async def agent_run(request: AgentRunRequest) -> dict[str, object]:
        result = await app.state.runtime.orchestrator.run(request.task, task_type=request.task_type)
        return asdict(result)

    @app.post("/memory/search")
    async def memory_search(request: MemorySearchRequest) -> dict[str, object]:
        results = app.state.runtime.memory.search(request.query, request.limit)
        return {"results": [asdict(item) for item in results]}

    @app.get("/memory/timeline")
    async def memory_timeline(limit: int = 50, include_archived: bool = False) -> dict[str, object]:
        return {"items": app.state.runtime.memory.timeline(limit=limit, include_archived=include_archived)}

    @app.get("/memory/recent")
    async def memory_recent(limit: int = 8) -> dict[str, object]:
        return {"context": app.state.runtime.memory.recent_context(limit=limit)}

    @app.get("/memory/summaries")
    async def memory_summaries(limit: int = 20) -> dict[str, object]:
        return {"items": app.state.runtime.memory.summaries(limit=limit)}

    @app.get("/memory/health")
    async def memory_health() -> dict[str, object]:
        return app.state.runtime.memory.health()

    @app.delete("/memory/{episode_id}")
    async def memory_delete(episode_id: int) -> dict[str, object]:
        return {"ok": app.state.runtime.memory.delete(episode_id)}

    @app.post("/memory/{episode_id}/pin")
    async def memory_pin(episode_id: int, request: MemoryPinRequest) -> dict[str, object]:
        return {"ok": app.state.runtime.memory.pin(episode_id, request.pinned)}

    @app.post("/memory/{episode_id}/archive")
    async def memory_archive(episode_id: int) -> dict[str, object]:
        return {"ok": app.state.runtime.memory.archive(episode_id)}

    @app.get("/telemetry")
    async def telemetry() -> dict[str, object]:
        return app.state.runtime.telemetry.snapshot()

    @app.get("/analytics/summary")
    async def analytics_summary() -> dict[str, object]:
        telemetry_snapshot = app.state.runtime.telemetry.snapshot()
        gauges = telemetry_snapshot.get("gauges", {})
        return {
            "workflow_learning": app.state.runtime.workflow_learning.summary(),
            "memory_health": app.state.runtime.memory.health(),
            "routing": {
                "confidence": gauges.get("routing_confidence", 0.0),
                "decisions": telemetry_snapshot.get("counters", {}).get("routing_decisions_total", 0),
            },
            "context": {
                "final_context_tokens": gauges.get("final_context_tokens", 0.0),
                "prompt_cost_estimate_tokens": gauges.get("prompt_cost_estimate_tokens", 0.0),
                "useful_recall_percent": gauges.get("memory_useful_recall_percent", 0.0),
                "irrelevant_recall_count": gauges.get("memory_irrelevant_recall_count", 0.0),
            },
        }

    @app.get("/workflows/templates")
    async def workflow_templates(limit: int = 8) -> dict[str, object]:
        return {"templates": app.state.runtime.workflow_learning.summary(limit=limit)["templates"]}

    @app.get("/state")
    async def state() -> dict[str, object]:
        return app.state.runtime.state.snapshot()

    @app.websocket("/state/ws")
    async def state_websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        last_version = -1
        while True:
            snapshot = app.state.runtime.state.snapshot()
            version = int(snapshot.get("version", 0))
            if version != last_version:
                await websocket.send_json(snapshot)
                last_version = version
            await asyncio.sleep(1.0)

    @app.get("/events/replay")
    async def event_replay(event_type: str | None = None, limit: int = 100) -> dict[str, object]:
        events = app.state.runtime.event_bus.replay(event_type=event_type, limit=limit)
        return {"events": [asdict(event) for event in events]}

    @app.get("/capabilities")
    async def capabilities() -> dict[str, object]:
        return {"capabilities": [capability.to_dict() for capability in app.state.runtime.capabilities.list()]}

    @app.post("/capabilities/recommend")
    async def recommend_capabilities(request: CapabilityRecommendRequest) -> dict[str, object]:
        plan = app.state.runtime.capability_recommendations.recommend(
            request.goal,
            max_ram_mb=request.max_ram_mb,
            permissions=set(request.permissions),
        )
        return plan.to_dict()

    @app.get("/reflection")
    async def reflection() -> dict[str, object]:
        return app.state.runtime.reflection.snapshot()

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(app.state.runtime.telemetry.prometheus_text(), media_type="text/plain")

    @app.post("/tools/run")
    async def run_tool(request: ToolRunRequest) -> dict[str, object]:
        result = await app.state.runtime.tools.run(request.name, request.payload)
        return asdict(result)

    @app.post("/voice/transcribe")
    async def voice_transcribe(request: Request) -> dict[str, object]:
        payload = await request.body()
        if not payload:
            return {"ok": False, "error": "empty_audio_payload"}
        suffix = ".webm" if "webm" in request.headers.get("content-type", "") else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
            handle.write(payload)
            path = handle.name
        try:
            chunks = await FasterWhisperTranscriber(model_size="base.en", compute_type="int8").transcribe_file(path)
            text = " ".join(chunk.text.strip() for chunk in chunks).strip()
            return {"ok": True, "text": text, "chunks": [asdict(chunk) for chunk in chunks]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            Path(path).unlink(missing_ok=True)

    @app.post("/workflows/coding")
    async def workflow_coding(request: WorkflowRunRequest) -> dict[str, object]:
        result = await app.state.runtime.workflows.run_coding(request.goal)
        return result.to_dict()

    @app.post("/workflows/research")
    async def workflow_research(request: WorkflowRunRequest) -> dict[str, object]:
        result = await app.state.runtime.workflows.run_research(request.goal, request.seed_sources or None)
        return result.to_dict()

    @app.post("/workflows/planner")
    async def workflow_planner(request: WorkflowRunRequest) -> dict[str, object]:
        result = await app.state.runtime.workflows.run_planner(request.goal)
        return result.to_dict()

    @app.websocket("/ws")
    async def websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        while True:
            message = await websocket.receive_text()
            result = await app.state.runtime.orchestrator.run(message)
            await websocket.send_json(asdict(result))

    return app


def _sse(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"
