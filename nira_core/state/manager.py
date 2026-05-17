from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ActiveTask:
    """One task currently being orchestrated or processed by a worker."""

    id: str
    kind: str
    created_at: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    """Worker pool health and utilization information."""

    name: str
    status: str
    concurrency: int
    active: int = 0
    last_seen: float = field(default_factory=time.time)


class SystemState:
    """Thread-safe singleton state store for adaptive orchestration."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_model: str | None = None
        self._resident_models: set[str] = set()
        self._ram_usage_mb = 0.0
        self._cpu_usage = 0.0
        self._queue_depth: dict[str, int] = {}
        self._active_tasks: dict[str, ActiveTask] = {}
        self._latency_ms: dict[str, float] = {}
        self._compression_ratio = 1.0
        self._hallucination_score = 0.0
        self._retrieval_precision = 0.0
        self._worker_health: dict[str, WorkerHealth] = {}
        self._capability_performance: dict[str, dict[str, float]] = {}
        self._routing_quality: dict[str, float] = {}
        self._version = 0
        self._updated_at = time.time()

    def clear(self) -> None:
        """Reset runtime state while preserving the singleton instance."""

        with self._lock:
            self._active_model = None
            self._resident_models.clear()
            self._ram_usage_mb = 0.0
            self._cpu_usage = 0.0
            self._queue_depth.clear()
            self._active_tasks.clear()
            self._latency_ms.clear()
            self._compression_ratio = 1.0
            self._hallucination_score = 0.0
            self._retrieval_precision = 0.0
            self._worker_health.clear()
            self._capability_performance.clear()
            self._routing_quality.clear()
            self._version = 0
            self._updated_at = time.time()

    def set_resources(self, ram_usage_mb: float, cpu_usage: float) -> None:
        with self._lock:
            self._ram_usage_mb = float(ram_usage_mb)
            self._cpu_usage = float(cpu_usage)
            self._touch()

    def set_active_model(self, alias: str | None) -> None:
        with self._lock:
            self._active_model = alias
            if alias:
                self._resident_models.add(alias)
            self._touch()

    def add_resident_model(self, alias: str) -> None:
        with self._lock:
            self._resident_models.add(alias)
            self._touch()

    def remove_resident_model(self, alias: str) -> None:
        with self._lock:
            self._resident_models.discard(alias)
            if self._active_model == alias:
                self._active_model = None
            self._touch()

    def set_queue_depth(self, queue_name: str, depth: int) -> None:
        with self._lock:
            self._queue_depth[queue_name] = max(0, int(depth))
            self._touch()

    def start_task(self, task_id: str, kind: str, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._active_tasks[task_id] = ActiveTask(
                id=task_id,
                kind=kind,
                created_at=time.time(),
                metadata=metadata or {},
            )
            self._touch()

    def finish_task(self, task_id: str) -> None:
        with self._lock:
            self._active_tasks.pop(task_id, None)
            self._touch()

    def record_latency(self, name: str, latency_ms: float) -> None:
        with self._lock:
            self._latency_ms[name] = float(latency_ms)
            self._touch()

    def record_compression(self, ratio: float) -> None:
        with self._lock:
            self._compression_ratio = float(ratio)
            self._touch()

    def record_hallucination_score(self, score: float) -> None:
        with self._lock:
            self._hallucination_score = _clamp(score)
            self._touch()

    def record_retrieval_precision(self, precision: float) -> None:
        with self._lock:
            self._retrieval_precision = _clamp(precision)
            self._touch()

    def set_worker_health(self, name: str, status: str, concurrency: int, active: int = 0) -> None:
        with self._lock:
            self._worker_health[name] = WorkerHealth(
                name=name,
                status=status,
                concurrency=max(1, int(concurrency)),
                active=max(0, int(active)),
            )
            self._touch()

    def record_capability_performance(self, name: str, latency_ms: float, success: bool) -> None:
        with self._lock:
            current = self._capability_performance.setdefault(
                name,
                {"calls": 0.0, "successes": 0.0, "avg_latency_ms": 0.0},
            )
            calls = current["calls"] + 1.0
            current["avg_latency_ms"] = ((current["avg_latency_ms"] * current["calls"]) + latency_ms) / calls
            current["calls"] = calls
            current["successes"] += 1.0 if success else 0.0
            self._touch()

    def record_routing_quality(self, route: str, score: float) -> None:
        with self._lock:
            self._routing_quality[route] = _clamp(score)
            self._touch()

    async def async_snapshot(self) -> dict[str, Any]:
        """Async-friendly state snapshot for websocket endpoints."""

        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable state snapshot."""

        with self._lock:
            return {
                "active_model": self._active_model,
                "resident_models": sorted(self._resident_models),
                "ram_usage_mb": self._ram_usage_mb,
                "cpu_usage": self._cpu_usage,
                "queue_depth": dict(self._queue_depth),
                "active_tasks": [asdict(task) for task in self._active_tasks.values()],
                "latency_ms": dict(self._latency_ms),
                "compression_ratio": self._compression_ratio,
                "hallucination_score": self._hallucination_score,
                "retrieval_precision": self._retrieval_precision,
                "worker_health": {name: asdict(health) for name, health in self._worker_health.items()},
                "capability_performance": {name: dict(values) for name, values in self._capability_performance.items()},
                "routing_quality": dict(self._routing_quality),
                "version": self._version,
                "updated_at": self._updated_at,
            }

    def _touch(self) -> None:
        self._version += 1
        self._updated_at = time.time()


_SYSTEM_STATE: SystemState | None = None
_SYSTEM_STATE_LOCK = threading.Lock()


def get_system_state() -> SystemState:
    """Return the process-wide runtime state singleton."""

    global _SYSTEM_STATE
    if _SYSTEM_STATE is None:
        with _SYSTEM_STATE_LOCK:
            if _SYSTEM_STATE is None:
                _SYSTEM_STATE = SystemState()
    return _SYSTEM_STATE


def reset_system_state() -> SystemState:
    """Clear and return the process-wide runtime state singleton."""

    state = get_system_state()
    state.clear()
    return state


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
