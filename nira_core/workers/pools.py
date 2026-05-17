from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from nira_core.events import Event, EventBus, EventType
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry
from nira_core.workers.queues import InMemoryTaskQueue, TaskEnvelope


TaskHandler = Callable[[TaskEnvelope], Awaitable[None]]


class WorkerPool:
    """Bounded asyncio worker pool with queue latency metrics."""

    def __init__(
        self,
        name: str,
        queue: InMemoryTaskQueue,
        concurrency: int,
        handler: TaskHandler,
        telemetry: Telemetry,
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
        task_timeout_sec: float = 120.0,
    ) -> None:
        self.name = name
        self._queue = queue
        self._concurrency = max(1, concurrency)
        self._handler = handler
        self._telemetry = telemetry
        self._state = state
        self._event_bus = event_bus
        self._task_timeout_sec = max(1.0, task_timeout_sec)
        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()
        self._active = 0
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        for index in range(self._concurrency):
            self._spawn_worker(index)
        self._record_health("running")
        self._telemetry.emit("worker_pool.start", {"name": self.name, "concurrency": self._concurrency})

    async def stop(self) -> None:
        if not self._started:
            self._record_health("stopped")
            return
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._started = False
        self._record_health("stopped")
        self._telemetry.emit("worker_pool.stop", {"name": self.name})

    def _spawn_worker(self, index: int) -> None:
        task = asyncio.create_task(self._run_worker(index))
        task.add_done_callback(lambda completed, worker_index=index: self._restart_worker(worker_index, completed))
        self._tasks.append(task)

    def _restart_worker(self, index: int, task: asyncio.Task[None]) -> None:
        if self._stopping.is_set() or task.cancelled():
            return
        exc = task.exception()
        self._tasks = [item for item in self._tasks if item is not task]
        if exc is not None:
            self._telemetry.increment("worker_restarts_total")
            self._telemetry.emit("worker.restart", {"pool": self.name, "worker": index, "error": str(exc)})
        self._spawn_worker(index)

    async def _run_worker(self, index: int) -> None:
        while not self._stopping.is_set():
            task = await self._queue.dequeue()
            self._telemetry.observe("queue_latency_seconds", time.time() - task.created_at)
            self._telemetry.emit("worker.task.start", {"pool": self.name, "worker": index, "kind": task.kind})
            self._active += 1
            self._record_health("running")
            try:
                await asyncio.wait_for(self._handler(task), timeout=self._task_timeout_sec)
                self._telemetry.increment("task_success_total")
            except asyncio.TimeoutError:
                self._telemetry.increment("task_timeout_total")
                self._telemetry.emit(
                    "worker.task.timeout",
                    {"pool": self.name, "kind": task.kind, "attempts": task.attempts, "max_retries": task.max_retries},
                )
                if task.attempts < task.max_retries:
                    self._telemetry.increment("task_retries_total")
                    await asyncio.sleep(_retry_delay(task.attempts))
                    await self._queue.enqueue(task.retry())
            except Exception as exc:
                self._telemetry.increment("task_failure_total")
                self._telemetry.emit(
                    "worker.task.error",
                    {"pool": self.name, "error": str(exc), "attempts": task.attempts, "max_retries": task.max_retries},
                )
                if task.attempts < task.max_retries and task.payload.get("retryable", True):
                    self._telemetry.increment("task_retries_total")
                    await asyncio.sleep(_retry_delay(task.attempts))
                    await self._queue.enqueue(task.retry())
            finally:
                self._active = max(0, self._active - 1)
                self._record_health("running")

    def _record_health(self, status: str) -> None:
        if self._state is not None:
            self._state.set_worker_health(self.name, status, self._concurrency, self._active)
        if self._event_bus is not None:
            self._event_bus.publish_nowait(
                Event.create(
                    EventType.WORKER_UPDATED,
                    {"pool": self.name, "status": status, "active": self._active, "concurrency": self._concurrency},
                )
            )


def _retry_delay(attempts: int) -> float:
    return min(5.0, 0.25 * (2 ** max(0, attempts)))
