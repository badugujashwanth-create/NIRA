from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EventType(StrEnum):
    """Canonical event names used across orchestration layers."""

    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    COMPRESSION_COMPLETED = "compression.completed"
    INFERENCE_STARTED = "inference.started"
    INFERENCE_COMPLETED = "inference.completed"
    TOOL_FAILED = "tool.failed"
    MEMORY_UPDATED = "memory.updated"
    ROUTING_CHANGED = "routing.changed"
    MODEL_SWAPPED = "model.swapped"
    CAPABILITY_PLANNED = "capability.planned"
    REFLECTION_APPLIED = "reflection.applied"
    WORKER_UPDATED = "worker.updated"


@dataclass(frozen=True, slots=True)
class Event:
    """Typed event persisted and published through the event bus."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = field(default_factory=time.time)
    trace_id: str | None = None

    @classmethod
    def create(
        cls,
        event_type: EventType | str,
        payload: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> Event:
        name = event_type.value if isinstance(event_type, EventType) else str(event_type)
        return cls(type=name, payload=payload or {}, trace_id=trace_id)
