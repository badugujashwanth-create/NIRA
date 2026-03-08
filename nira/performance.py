from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class PerformanceLimits:
    cpu_throttle_ms: int
    inference_cooldown_ms: int
    max_context_chars: int


class PerformanceGuard:
    def __init__(self, limits: PerformanceLimits) -> None:
        self.limits = limits
        self._last_inference_ts = 0.0
        self._lock = threading.Lock()
        self._rate_capacity = 2.0
        self._rate_tokens = self._rate_capacity
        self._rate_refill_per_sec = 1.0 / max(0.001, self.limits.inference_cooldown_ms / 1000.0)
        self._last_refill_ts = time.monotonic()

    def throttle_cpu(self) -> None:
        time.sleep(max(0, self.limits.cpu_throttle_ms) / 1000.0)

    def wait_for_inference_slot(self, timeout_sec: float = 5.0) -> bool:
        deadline = time.monotonic() + max(0.1, timeout_sec)
        while time.monotonic() < deadline:
            with self._lock:
                self._refill_tokens_locked()
                if self._rate_tokens >= 1.0:
                    self._rate_tokens -= 1.0
                    self._last_inference_ts = time.time()
                    return True
            time.sleep(0.01)
        return False

    def _refill_tokens_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill_ts
        if elapsed <= 0:
            return
        self._rate_tokens = min(self._rate_capacity, self._rate_tokens + elapsed * self._rate_refill_per_sec)
        self._last_refill_ts = now

    def clamp_context(self, text: str) -> str:
        if len(text) <= self.limits.max_context_chars:
            return text
        return text[-self.limits.max_context_chars :]

    @staticmethod
    def estimate_tokens(text: str) -> int:
        # Rough CPU-friendly token estimate to enforce limits quickly.
        return max(1, len(text) // 4)
