from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from nira_core.api import create_app
from nira_core.bootstrap import build_runtime
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text
from nira_core.runtime import RuntimeStartupManager, StartupCheck, run_demo


class FakeBackend:
    async def generate(self, spec, request: InferenceRequest):
        return result_from_text(f"fake:{spec.alias}", spec, request.prompt, time.perf_counter())

    async def unload(self, spec) -> None:
        return None


@pytest.mark.asyncio
async def test_startup_manager_starts_and_stops_workers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    runtime = build_runtime()
    manager = RuntimeStartupManager(runtime)

    async def fake_validate():
        return [StartupCheck("test", True, "ok")]

    monkeypatch.setattr(manager, "validate", fake_validate)
    report = await manager.start()
    assert report.ok is True
    assert runtime.workers.started is True
    await manager.stop()
    assert runtime.workers.started is False


@pytest.mark.asyncio
async def test_demo_mode_runs_without_ollama(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    runtime = build_runtime()
    result = await run_demo(runtime)
    assert "coding" in result
    assert result["state"]["queue_depth"]["inference"] == 7


def test_ui_and_memory_workflow_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    runtime = build_runtime()
    runtime.inference._backends["ollama"] = FakeBackend()
    app = create_app(runtime)

    with TestClient(app) as client:
        assert client.get("/ui").status_code == 200
        coding = client.post("/workflows/coding", json={"goal": "explain bounded context"})
        assert coding.status_code == 200
        assert coding.json()["workflow"] == "coding"

        timeline = client.get("/memory/timeline")
        assert timeline.status_code == 200
        items = timeline.json()["items"]
        assert items
        episode_id = items[0]["id"]
        assert client.post(f"/memory/{episode_id}/pin", json={"pinned": True}).json()["ok"] is True
        assert client.post(f"/memory/{episode_id}/archive").json()["ok"] is True
