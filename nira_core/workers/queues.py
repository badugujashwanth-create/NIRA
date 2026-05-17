from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from nira_core.events import Event, EventBus, EventType
from nira_core.state import SystemState


class QueueBackpressureError(RuntimeError):
    """Raised when a local queue reaches its configured depth limit."""


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    """Serializable task envelope used by Redis and in-memory queues."""

    kind: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_retries: int = 0

    def retry(self) -> TaskEnvelope:
        """Return a retry envelope preserving task identity."""

        return TaskEnvelope(
            kind=self.kind,
            payload=self.payload,
            id=self.id,
            created_at=time.time(),
            attempts=self.attempts + 1,
            max_retries=self.max_retries,
        )


class InMemoryTaskQueue:
    """Asyncio queue fallback for local tests or no-Redis development."""

    def __init__(
        self,
        name: str = "default",
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
        max_depth: int = 128,
    ) -> None:
        self.name = name
        self._state = state
        self._event_bus = event_bus
        self._max_depth = max(1, max_depth)
        self._queue: asyncio.Queue[TaskEnvelope] = asyncio.Queue()

    async def enqueue(self, task: TaskEnvelope) -> None:
        if self.depth() >= self._max_depth:
            if self._event_bus is not None:
                self._event_bus.publish_nowait(
                    Event.create(EventType.WORKER_UPDATED, {"queue": self.name, "depth": self.depth(), "backpressure": True})
                )
            raise QueueBackpressureError(f"Queue {self.name} is at capacity ({self._max_depth})")
        await self._queue.put(task)
        self._update_depth()

    async def dequeue(self) -> TaskEnvelope:
        task = await self._queue.get()
        self._update_depth()
        return task

    def depth(self) -> int:
        return self._queue.qsize()

    def _update_depth(self) -> None:
        depth = self.depth()
        if self._state is not None:
            self._state.set_queue_depth(self.name, depth)
        if self._event_bus is not None:
            self._event_bus.publish_nowait(Event.create(EventType.WORKER_UPDATED, {"queue": self.name, "depth": depth}))


class RedisTaskQueue:
    """Redis-backed task queue using redis.asyncio when available."""

    def __init__(self, redis_url: str, queue_name: str) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._client = None

    async def enqueue(self, task: TaskEnvelope) -> None:
        payload = json.dumps(asdict(task), default=str)
        try:
            client = await self._connect()
            await client.lpush(self._queue_name, payload)
        except Exception:
            self._client = None
            client = await self._connect()
            await client.lpush(self._queue_name, payload)

    async def dequeue(self) -> TaskEnvelope:
        try:
            client = await self._connect()
            _, raw = await client.brpop(self._queue_name)
        except Exception:
            self._client = None
            client = await self._connect()
            _, raw = await client.brpop(self._queue_name)
        data = json.loads(raw)
        return TaskEnvelope(
            kind=data["kind"],
            payload=data["payload"],
            id=data["id"],
            created_at=float(data["created_at"]),
            attempts=int(data.get("attempts", 0)),
            max_retries=int(data.get("max_retries", 0)),
        )

    async def _connect(self):
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError("Redis queues require redis. Install with: pip install -r requirements.txt") from exc
        self._client = redis.from_url(self._redis_url)
        return self._client
