from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceSample:
    """RAM and CPU sample for local observability."""

    ram_used_mb: float
    ram_percent: float
    cpu_percent: float


def sample_resources() -> ResourceSample:
    """Sample host resources with psutil when available."""

    try:
        import psutil
    except ImportError:
        return ResourceSample(ram_used_mb=0.0, ram_percent=0.0, cpu_percent=0.0)
    memory = psutil.virtual_memory()
    return ResourceSample(
        ram_used_mb=(memory.total - memory.available) / (1024 * 1024),
        ram_percent=float(memory.percent),
        cpu_percent=float(psutil.cpu_percent(interval=None)),
    )
