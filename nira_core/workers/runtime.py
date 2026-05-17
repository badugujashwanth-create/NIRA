from __future__ import annotations

from dataclasses import dataclass

from nira_core.config import NiraConfig
from nira_core.events import EventBus
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry
from nira_core.workers.pools import WorkerPool
from nira_core.workers.queues import InMemoryTaskQueue, TaskEnvelope


@dataclass(slots=True)
class WorkerRuntime:
    """Separate worker pools for CPU-bound and IO-bound task classes."""

    inference_queue: InMemoryTaskQueue
    retrieval_queue: InMemoryTaskQueue
    browser_queue: InMemoryTaskQueue
    compression_queue: InMemoryTaskQueue
    pools: list[WorkerPool]
    started: bool = False

    async def start(self) -> None:
        if self.started:
            return
        for pool in self.pools:
            await pool.start()
        self.started = True

    async def stop(self) -> None:
        if not self.started:
            return
        for pool in self.pools:
            await pool.stop()
        self.started = False


def build_worker_runtime(
    config: NiraConfig,
    telemetry: Telemetry,
    state: SystemState | None = None,
    event_bus: EventBus | None = None,
) -> WorkerRuntime:
    """Build queue-separated pools with serialized inference by default."""

    async def placeholder_handler(task: TaskEnvelope) -> None:
        telemetry.emit("worker.placeholder", {"kind": task.kind, "id": task.id})

    inference_queue = InMemoryTaskQueue("inference", state, event_bus, max_depth=config.workers.queue_max_depth)
    retrieval_queue = InMemoryTaskQueue("retrieval", state, event_bus, max_depth=config.workers.queue_max_depth)
    browser_queue = InMemoryTaskQueue("browser", state, event_bus, max_depth=config.workers.queue_max_depth)
    compression_queue = InMemoryTaskQueue("compression", state, event_bus, max_depth=config.workers.queue_max_depth)
    pools = [
        WorkerPool("inference", inference_queue, config.workers.inference_concurrency, placeholder_handler, telemetry, state, event_bus, config.workers.task_timeout_sec),
        WorkerPool("retrieval", retrieval_queue, config.workers.retrieval_concurrency, placeholder_handler, telemetry, state, event_bus, config.workers.task_timeout_sec),
        WorkerPool("browser", browser_queue, config.workers.browser_concurrency, placeholder_handler, telemetry, state, event_bus, config.workers.task_timeout_sec),
        WorkerPool("compression", compression_queue, config.workers.compression_concurrency, placeholder_handler, telemetry, state, event_bus, config.workers.task_timeout_sec),
    ]
    return WorkerRuntime(
        inference_queue=inference_queue,
        retrieval_queue=retrieval_queue,
        browser_queue=browser_queue,
        compression_queue=compression_queue,
        pools=pools,
    )
