from __future__ import annotations

import time

import psutil


class SystemMetrics:
    def snapshot(self) -> dict[str, float]:
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            "timestamp": time.time(),
            "cpu_percent": psutil.cpu_percent(interval=0.0),
            "memory_percent": psutil.virtual_memory().percent,
            "rss_mb": round(memory_info.rss / (1024 * 1024), 2),
        }
