from __future__ import annotations

import asyncio
import json
import time

from nira_core.bootstrap import NiraRuntime
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text


class DemoBackend:
    """Deterministic local backend for showcase mode without requiring Ollama."""

    async def generate(self, spec, request: InferenceRequest):
        text = (
            f"[demo:{spec.alias}] NIRA planned the task, retrieved bounded context, "
            "applied reflection policy, and produced this simulated response."
        )
        return result_from_text(text, spec, request.prompt, time.perf_counter())

    async def unload(self, spec) -> None:
        return None


async def run_demo(runtime: NiraRuntime) -> dict[str, object]:
    """Run a short deterministic showcase of workflows, memory, and telemetry."""

    runtime.inference._backends["ollama"] = DemoBackend()
    runtime.memory.remember_task("Demo seed", "NIRA stores durable bounded memories.", importance=0.9)
    runtime.state.set_queue_depth("inference", 7)
    runtime.reflection.optimize()
    coding = await runtime.workflows.run_coding("Explain how NIRA keeps context small.")
    research = await runtime.workflows.run_research(
        "Summarize local-first orchestration benefits.",
        seed_sources=[
            {
                "title": "Local-first AI operations",
                "url": "demo://local-first",
                "snippet": "Local-first systems reduce dependency on cloud services and improve data locality.",
            }
        ],
    )
    planner = await runtime.workflows.run_planner("Plan a safe browser research task and store the result.")
    return {
        "coding": coding.to_dict(),
        "research": research.to_dict(),
        "planner": planner.to_dict(),
        "state": runtime.state.snapshot(),
        "reflection": runtime.reflection.snapshot(),
        "events": [event.type for event in runtime.event_bus.replay(limit=20)],
        "telemetry": _compact_telemetry(runtime.telemetry.snapshot()),
    }


def print_demo(result: dict[str, object]) -> None:
    print(json.dumps(result, indent=2, default=str))


def _compact_telemetry(snapshot: dict[str, object]) -> dict[str, object]:
    return {
        "counters": snapshot.get("counters", {}),
        "gauges": snapshot.get("gauges", {}),
        "histograms": snapshot.get("histograms", {}),
    }
