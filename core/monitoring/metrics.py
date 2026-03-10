from __future__ import annotations

import time
from collections import Counter, defaultdict
from functools import wraps
from typing import Any, Callable


class MetricsCollector:
    def __init__(self) -> None:
        self.counters: Counter[str] = Counter()
        self.timings: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1) -> None:
        self.counters[name] += value

    def record_timing(self, name: str, seconds: float) -> None:
        self.timings[name].append(seconds)

    def summary(self) -> dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "timings": {
                key: {
                    "count": len(values),
                    "avg_ms": round((sum(values) / len(values)) * 1000, 2) if values else 0.0,
                    "max_ms": round(max(values) * 1000, 2) if values else 0.0,
                }
                for key, values in self.timings.items()
            },
        }


def timed(metrics: MetricsCollector, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                metrics.record_timing(name, time.perf_counter() - started)

        return wrapper

    return decorator
