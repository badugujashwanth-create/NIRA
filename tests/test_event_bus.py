from __future__ import annotations

import pytest

from nira_core.events import Event, EventBus, EventType
from nira_core.telemetry import Telemetry


@pytest.mark.asyncio
async def test_event_bus_publishes_persists_and_replays(tmp_path) -> None:
    telemetry = Telemetry(tmp_path / "telemetry")
    bus = EventBus(tmp_path / "events", telemetry)
    received: list[str] = []

    async def handler(event: Event) -> None:
        received.append(event.type)

    bus.subscribe(EventType.TASK_CREATED.value, handler)
    await bus.publish(Event.create(EventType.TASK_CREATED, {"task_id": "abc"}))

    assert received == [EventType.TASK_CREATED.value]
    replayed = bus.replay(EventType.TASK_CREATED.value)
    assert len(replayed) == 1
    assert replayed[0].payload["task_id"] == "abc"
    assert telemetry.snapshot()["counters"]["events_published_total"] == 1
