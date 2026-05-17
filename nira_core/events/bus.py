from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from nira_core.events.types import Event

if TYPE_CHECKING:
    from nira_core.telemetry import Telemetry


EventHandler = Callable[[Event], Awaitable[None] | None]


class EventBackend(Protocol):
    """Transport backend for event fan-out."""

    async def publish(self, event: Event) -> None:
        """Publish one event."""


class LocalEventBackend:
    """In-process fallback backend."""

    async def publish(self, event: Event) -> None:
        return None


class RedisPubSubBackend:
    """Redis pub/sub backend for decoupled local processes."""

    def __init__(self, redis_url: str, channel: str = "nira.events") -> None:
        self._redis_url = redis_url
        self._channel = channel
        self._client = None

    async def publish(self, event: Event) -> None:
        payload = json.dumps(asdict(event), default=str)
        try:
            client = await self._connect()
            await client.publish(self._channel, payload)
        except Exception:
            self._client = None
            client = await self._connect()
            await client.publish(self._channel, payload)

    async def _connect(self):
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise RuntimeError("Redis event backend requires redis. Install with: pip install -r requirements.txt") from exc
        self._client = redis.from_url(self._redis_url)
        return self._client


class EventBus:
    """Async publish/subscribe bus with JSONL persistence and replay."""

    def __init__(
        self,
        data_dir: Path,
        telemetry: "Telemetry | None" = None,
        backend: EventBackend | None = None,
        max_payload_chars: int = 2_000,
        telemetry_sample_interval_sec: float = 1.0,
    ) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._data_dir / "events.jsonl"
        self._telemetry = telemetry
        self._backend = backend or LocalEventBackend()
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []
        self._lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._max_payload_chars = max_payload_chars
        self._telemetry_sample_interval_sec = telemetry_sample_interval_sec
        self._last_telemetry_emit: dict[str, float] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type or '*' for all events."""

        if event_type == "*":
            self._wildcard_subscribers.append(handler)
        else:
            self._subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """Persist, publish, and dispatch an event."""

        started = time.perf_counter()
        event = self._bounded_event(event)
        await self._persist(event)
        try:
            await self._backend.publish(event)
        except Exception as exc:
            if self._telemetry is not None:
                self._telemetry.increment("event_backend_failures_total")
                self._telemetry.emit("event.backend_error", {"event_type": event.type, "error": str(exc)})
        handlers = [*self._subscribers.get(event.type, []), *self._wildcard_subscribers]
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await asyncio.wait_for(result, timeout=5.0)
            except Exception as exc:
                if self._telemetry is not None:
                    self._telemetry.increment("event_handler_failures_total")
                    self._telemetry.emit("event.handler_error", {"event_type": event.type, "error": str(exc)})
        latency = (time.perf_counter() - started) * 1000.0
        if self._telemetry is not None:
            self._telemetry.increment("events_published_total")
            self._telemetry.observe("event_publish_latency_ms", latency)
            if self._should_emit_event_telemetry(event.type):
                self._telemetry.emit("event.published", {"event_type": event.type, "event_id": event.id})

    def publish_nowait(self, event: Event) -> None:
        """Publish from sync code when an event loop may or may not be running."""

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.publish(event))
            return
        task = loop.create_task(self.publish(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._on_background_done)

    def _on_background_done(self, task: asyncio.Task[None]) -> None:
        self._background_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.exception()
        except Exception:
            return

    async def drain(self) -> None:
        """Wait for background publish tasks to finish during graceful shutdown."""

        if self._background_tasks:
            await asyncio.gather(*list(self._background_tasks), return_exceptions=True)

    def replay(self, event_type: str | None = None, limit: int = 100) -> list[Event]:
        """Replay persisted events from newest bounded history."""

        if not self._events_path.exists():
            return []
        lines = self._events_path.read_text(encoding="utf-8").splitlines()
        events: list[Event] = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            data = json.loads(line)
            event = Event(
                type=data["type"],
                payload=data.get("payload", {}),
                id=data["id"],
                timestamp=float(data["timestamp"]),
                trace_id=data.get("trace_id"),
            )
            if event_type is None or event.type == event_type:
                events.append(event)
        return events

    async def _persist(self, event: Event) -> None:
        line = json.dumps(asdict(event), sort_keys=True, default=str)
        async with self._lock:
            self._events_path.parent.mkdir(parents=True, exist_ok=True)
            with self._events_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _bounded_event(self, event: Event) -> Event:
        payload = dict(event.payload)
        for key, value in list(payload.items()):
            rendered = json.dumps(value, default=str)
            if len(rendered) > self._max_payload_chars:
                payload[key] = rendered[: self._max_payload_chars] + "...[truncated]"
        return Event(type=event.type, payload=payload, id=event.id, timestamp=event.timestamp, trace_id=event.trace_id)

    def _should_emit_event_telemetry(self, event_type: str) -> bool:
        now = time.monotonic()
        previous = self._last_telemetry_emit.get(event_type, 0.0)
        if now - previous < self._telemetry_sample_interval_sec:
            return False
        self._last_telemetry_emit[event_type] = now
        return True
