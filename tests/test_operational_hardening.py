from __future__ import annotations

import pytest

import system_validation
from nira_core.compression import ContextBudgeter, ContextDistillationPipeline, SemanticCompressor
from nira_core.config import load_config
from nira_core.events import Event, EventBus
from nira_core.memory import MemoryManager
from nira_core.retrieval import BGEReranker, RetrievalPipeline
from nira_core.telemetry import Telemetry
from nira_core.workers import InMemoryTaskQueue, QueueBackpressureError, TaskEnvelope


@pytest.mark.asyncio
async def test_event_bus_throttles_event_telemetry_and_drains(tmp_path) -> None:
    telemetry = Telemetry(tmp_path / "telemetry")
    bus = EventBus(tmp_path / "events", telemetry, telemetry_sample_interval_sec=60.0)
    for index in range(3):
        bus.publish_nowait(Event.create("test.event", {"index": index}))
    await bus.drain()

    assert len(bus.replay(limit=10)) == 3
    event_logs = [event for event in telemetry.snapshot()["recent_events"] if event["name"] == "event.published"]
    assert len(event_logs) == 1


@pytest.mark.asyncio
async def test_queue_backpressure_rejects_over_capacity() -> None:
    queue = InMemoryTaskQueue("test", max_depth=1)
    await queue.enqueue(TaskEnvelope(kind="a", payload={}))
    with pytest.raises(QueueBackpressureError):
        await queue.enqueue(TaskEnvelope(kind="b", payload={}))


@pytest.mark.asyncio
async def test_context_distillation_removes_duplicate_chunks(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    config = load_config()
    telemetry = Telemetry(tmp_path / "telemetry")
    memory = MemoryManager(config, telemetry)
    duplicate = "Duplicate context about bounded prompts and retrieval precision."
    memory.semantic.add("a", duplicate, {"kind": "doc"})
    memory.semantic.add("b", duplicate, {"kind": "doc"})
    retrieval = RetrievalPipeline(memory, BGEReranker(), telemetry)
    pipeline = ContextDistillationPipeline(retrieval, SemanticCompressor(None, telemetry), ContextBudgeter(120), telemetry)

    distilled = await pipeline.build_context("bounded prompts")
    assert distilled.context_tokens <= 120
    assert telemetry.snapshot()["counters"].get("retrieval_duplicates_removed_total", 0) >= 1


def test_memory_deduplicates_and_reports_health(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    config = load_config()
    memory = MemoryManager(config, Telemetry(tmp_path / "telemetry"))
    memory.remember_task("same", "same result", 0.5)
    memory.remember_task("same", "same result", 0.7)

    assert len(memory.timeline()) == 1
    health = memory.health()
    assert health["active"] == 1
    assert "fragmentation" in health


@pytest.mark.asyncio
async def test_full_validation_mode_returns_success(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NIRA_DATA_DIR", str(tmp_path / "data"))
    code = await system_validation.main_async(full=True)
    assert code == 0
