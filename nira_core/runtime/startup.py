from __future__ import annotations

import asyncio
import importlib.util
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nira_core.bootstrap import NiraRuntime
from nira_core.telemetry import sample_resources


@dataclass(frozen=True, slots=True)
class StartupCheck:
    """One startup validation check."""

    name: str
    ok: bool
    details: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class StartupReport:
    """Startup health report rendered by CLI and API."""

    ok: bool
    started_at: float
    checks: list[StartupCheck] = field(default_factory=list)
    ui_url: str = "http://127.0.0.1:8787"
    api_url: str = "http://127.0.0.1:8787"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "started_at": self.started_at,
            "checks": [asdict(check) for check in self.checks],
            "ui_url": self.ui_url,
            "api_url": self.api_url,
        }


class RuntimeStartupManager:
    """Coordinates dependency validation, worker lifecycle, and graceful shutdown."""

    def __init__(self, runtime: NiraRuntime, host: str = "127.0.0.1", port: int = 8787) -> None:
        self.runtime = runtime
        self.host = host
        self.port = port
        self._started = False
        self._maintenance_task: asyncio.Task[None] | None = None

    async def start(self) -> StartupReport:
        """Validate dependencies, initialize persistent stores, and start workers."""

        checks = await self.validate()
        self.runtime.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.runtime.config.tools.sandbox_root.mkdir(parents=True, exist_ok=True)
        self.runtime.memory.maintain()
        await self.runtime.workers.start()
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
        self._started = True
        resources = sample_resources()
        self.runtime.state.set_resources(resources.ram_used_mb, resources.cpu_percent)
        self.runtime.telemetry.emit("runtime.start", {"host": self.host, "port": self.port})
        return StartupReport(
            ok=all(check.ok or not check.required for check in checks),
            started_at=time.time(),
            checks=checks,
            ui_url=f"http://{self.host}:{self.port}/ui",
            api_url=f"http://{self.host}:{self.port}",
        )

    async def stop(self) -> None:
        """Gracefully stop worker pools and record shutdown telemetry."""

        if not self._started:
            return
        if self._maintenance_task is not None:
            self._maintenance_task.cancel()
            await asyncio.gather(self._maintenance_task, return_exceptions=True)
            self._maintenance_task = None
        await self.runtime.workers.stop()
        await self.runtime.event_bus.drain()
        self.runtime.telemetry.emit("runtime.stop", {})
        self._started = False

    async def _maintenance_loop(self) -> None:
        """Periodic low-cost cleanup for long-running daily sessions."""

        while True:
            await asyncio.sleep(300.0)
            try:
                self.runtime.memory.maintain()
                resources = sample_resources()
                self.runtime.state.set_resources(resources.ram_used_mb, resources.cpu_percent)
                if resources.ram_used_mb > self.runtime.config.runtime.ram_limit_mb:
                    await self.runtime.inference.unload_current_heavy("ram_pressure")
                self.runtime.reflection.optimize()
            except Exception as exc:
                self.runtime.telemetry.increment("maintenance_failures_total")
                self.runtime.telemetry.emit("runtime.maintenance_error", {"error": str(exc)})

    async def validate(self) -> list[StartupCheck]:
        """Run dependency checks without crashing on optional subsystem failures."""

        checks = [
            self._check_python_package("fastapi", required=True),
            self._check_python_package("uvicorn", required=True),
            self._check_python_package("httpx", required=True),
            self._check_python_package("chromadb", required=False),
            self._check_python_package("playwright", required=False),
            self._check_python_package("faster_whisper", required=False),
            self._check_paths(),
        ]
        checks.extend(await asyncio.gather(self._check_ollama(), self._check_redis()))
        for check in checks:
            self.runtime.telemetry.emit("startup.check", asdict(check))
        return checks

    def _check_python_package(self, package: str, required: bool) -> StartupCheck:
        ok = importlib.util.find_spec(package) is not None
        details = "available" if ok else f"missing package: {package}"
        return StartupCheck(name=f"python:{package}", ok=ok, details=details, required=required)

    def _check_paths(self) -> StartupCheck:
        try:
            self.runtime.config.data_dir.mkdir(parents=True, exist_ok=True)
            self.runtime.config.tools.sandbox_root.mkdir(parents=True, exist_ok=True)
            probe = Path(self.runtime.config.data_dir) / ".startup_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return StartupCheck("local_paths", True, "data and sandbox paths are writable")
        except Exception as exc:
            return StartupCheck("local_paths", False, str(exc), required=True)

    async def _check_ollama(self) -> StartupCheck:
        try:
            import httpx

            async with httpx.AsyncClient(base_url=self.runtime.config.runtime.ollama_base_url, timeout=3.0) as client:
                response = await client.get("/api/tags")
            if response.status_code != 200:
                return StartupCheck("ollama", False, f"HTTP {response.status_code}", required=False)
            available = {item.get("name") for item in response.json().get("models", [])}
            configured = {spec.name for spec in self.runtime.config.models.values() if spec.provider == "ollama"}
            missing = sorted(name for name in configured if name not in available)
            if missing:
                return StartupCheck("ollama", True, f"reachable; missing models: {', '.join(missing)}", required=False)
            return StartupCheck("ollama", True, "reachable; configured models present", required=False)
        except Exception as exc:
            return StartupCheck("ollama", False, f"unreachable: {exc}", required=False)

    async def _check_redis(self) -> StartupCheck:
        try:
            import redis.asyncio as redis

            client = redis.from_url(self.runtime.config.workers.redis_url)
            await client.ping()
            await client.aclose()
            return StartupCheck("redis", True, "reachable", required=False)
        except Exception as exc:
            return StartupCheck("redis", False, f"using in-memory queue fallback: {exc}", required=False)
