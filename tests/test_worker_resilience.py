from __future__ import annotations

import pytest

from nira_core.events import EventBus
from nira_core.state import reset_system_state
from nira_core.telemetry import Telemetry
from nira_core.workers import InMemoryTaskQueue, TaskEnvelope, WorkerPool


@pytest.mark.asyncio
async def test_worker_failure_injection_records_failure_and_recovers(tmp_path) -> None:
    telemetry = Telemetry(tmp_path / "telemetry")
    state = reset_system_state()
    bus = EventBus(tmp_path / "events", telemetry)
    queue = InMemoryTaskQueue("inference", state, bus)
    calls = {"count": 0}

    async def handler(task: TaskEnvelope) -> None:
        calls["count"] += 1
        if task.payload.get("fail"):
            raise RuntimeError("injected")

    pool = WorkerPool("inference", queue, 1, handler, telemetry, state, bus)
    await pool.start()
    await queue.enqueue(TaskEnvelope(kind="test", payload={"fail": True}))
    await queue.enqueue(TaskEnvelope(kind="test", payload={"fail": False}))

    for _ in range(50):
        if calls["count"] >= 2:
            break
        await __import__("asyncio").sleep(0.02)

    await pool.stop()
    counters = telemetry.snapshot()["counters"]
    assert counters["task_failure_total"] == 1
    assert counters["task_success_total"] == 1
    assert state.snapshot()["worker_health"]["inference"]["status"] == "stopped"
