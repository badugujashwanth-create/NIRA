from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nira_core.inference.base import InferenceResult
    from nira_core.state import SystemState


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    """A single structured telemetry event."""

    name: str
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)


class Telemetry:
    """Small local telemetry collector with Prometheus text export."""

    def __init__(self, data_dir: Path, logger_name: str = "nira_core") -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._data_dir / "events.jsonl"
        self._lock = threading.Lock()
        self._counters: Counter[str] = Counter()
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._events: list[TelemetryEvent] = []
        self._state: SystemState | None = None
        self._logger = logging.getLogger(logger_name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        console_logs = os.getenv("NIRA_CONSOLE_LOGS", "").lower() in {"1", "true", "yes", "on"}
        self._logger.setLevel(logging.INFO if console_logs else logging.WARNING)

    def register_state(self, state: SystemState) -> None:
        """Expose system state through telemetry snapshots and metrics."""

        self._state = state

    def emit(self, name: str, payload: dict[str, Any] | None = None) -> None:
        """Persist and log a structured event."""

        event = TelemetryEvent(name=name, timestamp=time.time(), payload=payload or {})
        line = json.dumps(asdict(event), sort_keys=True, default=str)
        with self._lock:
            self._events.append(event)
            with self._events_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        self._logger.info(line)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._histograms.setdefault(name, []).append(float(value))

    def record_inference(self, result: "InferenceResult") -> None:
        """Record standard inference metrics."""

        self.observe("inference_duration_seconds", result.duration_sec)
        self.gauge("inference_tokens_per_second", result.tokens_per_sec)
        self.gauge("context_size_tokens", result.token_accounting.prompt_tokens)
        self.increment("inference_requests_total")

    def snapshot(self) -> dict[str, Any]:
        """Return current local metrics for API responses."""

        with self._lock:
            snapshot = {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    key: {
                        "count": len(values),
                        "sum": sum(values),
                        "last": values[-1] if values else 0.0,
                    }
                    for key, values in self._histograms.items()
                },
                "recent_events": [asdict(event) for event in self._events[-50:]],
            }
        if self._state is not None:
            snapshot["system_state"] = self._state.snapshot()
        return snapshot

    def prometheus_text(self) -> str:
        """Render metrics in Prometheus text exposition format."""

        lines: list[str] = []
        snapshot = self.snapshot()
        for name, value in snapshot["counters"].items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
        for name, value in snapshot["gauges"].items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        for name, values in snapshot["histograms"].items():
            lines.append(f"# TYPE {name} summary")
            lines.append(f"{name}_count {values['count']}")
            lines.append(f"{name}_sum {values['sum']}")
        state = snapshot.get("system_state", {})
        if isinstance(state, dict):
            for name in ("ram_usage_mb", "cpu_usage", "compression_ratio", "hallucination_score", "retrieval_precision"):
                value = state.get(name)
                if isinstance(value, (int, float)):
                    metric_name = f"nira_state_{name}"
                    lines.append(f"# TYPE {metric_name} gauge")
                    lines.append(f"{metric_name} {float(value)}")
            queue_depth = state.get("queue_depth", {})
            if isinstance(queue_depth, dict):
                for queue_name, depth in queue_depth.items():
                    lines.append("# TYPE nira_queue_depth gauge")
                    lines.append(f'nira_queue_depth{{queue="{queue_name}"}} {float(depth)}')
        return "\n".join(lines) + "\n"
