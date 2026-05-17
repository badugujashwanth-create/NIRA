from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from nira_core.api import create_app
from nira_core.bootstrap import build_runtime
from nira_core.config import load_config
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text
from nira_core.routing import TaskRouter
from nira_core.telemetry import Telemetry


class LongFakeBackend:
    async def generate(self, spec, request: InferenceRequest):
        return result_from_text(
            f"fake:{spec.alias}: reusable daily workflow result with enough detail to pass quality scoring.",
            spec,
            request.prompt,
            time.perf_counter(),
        )

    async def unload(self, spec) -> None:
        return None


@pytest.mark.asyncio
async def test_repeated_workflow_uses_learning_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NIRA_DISABLE_CHROMA", "1")
    runtime = build_runtime()
    runtime.inference._backends["ollama"] = LongFakeBackend()

    first = await runtime.workflows.run_coding("Explain how NIRA should keep context bounded.")
    second = await runtime.workflows.run_coding("Explain how NIRA should keep context bounded.")

    assert first.metadata["cache_hit"] is False
    assert second.metadata["cache_hit"] is True
    summary = runtime.workflow_learning.summary()
    assert summary["cache"]["hits"] >= 1


@pytest.mark.asyncio
async def test_simple_classification_uses_fast_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NIRA_DISABLE_CHROMA", "1")
    runtime = build_runtime()
    runtime.inference._backends["ollama"] = LongFakeBackend()

    result = await runtime.orchestrator.run("Ping status", task_type="classification")

    assert result.context_tokens == 0
    assert runtime.telemetry.snapshot()["counters"].get("orchestration_fast_path_total", 0) >= 1


def test_route_decision_includes_confidence_and_cost(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    config = load_config()
    router = TaskRouter(config, Telemetry(tmp_path / "telemetry"))

    decision = router.route("summarize this short note")

    assert 0.0 < decision.confidence <= 1.0
    assert decision.complexity in {"low", "normal", "high"}
    assert decision.estimated_cost in {"low", "medium", "heavy", "unknown"}


def test_analytics_endpoint_exposes_usage_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NIRA_DISABLE_CHROMA", "1")
    runtime = build_runtime()
    app = create_app(runtime)

    with TestClient(app) as client:
        response = client.get("/analytics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert "workflow_learning" in payload
    assert "routing" in payload
    assert "context" in payload
