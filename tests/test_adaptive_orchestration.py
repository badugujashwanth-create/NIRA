from __future__ import annotations

import time

import pytest

from nira_core.bootstrap import build_runtime
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text


class FakeBackend:
    async def generate(self, spec, request: InferenceRequest):
        return result_from_text("bounded adaptive result", spec, request.prompt, time.perf_counter())

    async def unload(self, spec) -> None:
        return None


@pytest.mark.asyncio
async def test_orchestration_emits_events_and_updates_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    runtime = build_runtime()
    runtime.inference._backends["ollama"] = FakeBackend()

    result = await runtime.orchestrator.run("write Python tests for adaptive routing", task_type="coding")

    assert result.text == "bounded adaptive result"
    snapshot = runtime.state.snapshot()
    assert snapshot["active_tasks"] == []
    assert snapshot["active_model"] == "primary_coding"
    assert snapshot["latency_ms"]["orchestration"] >= 0
    event_types = [event.type for event in runtime.event_bus.replay(limit=20)]
    assert "task.created" in event_types
    assert "task.completed" in event_types
    assert "inference.completed" in event_types
    assert result.metadata["capability_plan"]
