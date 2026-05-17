from __future__ import annotations

import asyncio
import argparse
import importlib.util
import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from nira_core.bootstrap import build_runtime
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text
from nira_core.runtime import RuntimeStartupManager
from nira_core.workers import InMemoryTaskQueue, QueueBackpressureError, TaskEnvelope, WorkerPool


ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    name: str
    ok: bool
    details: str


class ValidationBackend:
    async def generate(self, spec, request: InferenceRequest):
        return result_from_text(
            f"validation:{spec.alias}: stable local workflow response with bounded context and operational analytics.",
            spec,
            request.prompt,
            time.perf_counter(),
        )

    async def unload(self, spec) -> None:
        return None


class FailingBackend:
    async def generate(self, spec, request: InferenceRequest):
        raise RuntimeError("validation failure")

    async def unload(self, spec) -> None:
        return None


def package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


async def main_async(full: bool = False) -> int:
    if full and not os.getenv("NIRA_DATA_DIR"):
        previous = os.environ.get("NIRA_DATA_DIR")
        previous_chroma = os.environ.get("NIRA_DISABLE_CHROMA")
        with tempfile.TemporaryDirectory(prefix="nira-validation-", ignore_cleanup_errors=True) as tmp:
            os.environ["NIRA_DATA_DIR"] = tmp
            os.environ["NIRA_DISABLE_CHROMA"] = "1"
            try:
                return await main_async(full=True)
            finally:
                if previous is None:
                    os.environ.pop("NIRA_DATA_DIR", None)
                else:
                    os.environ["NIRA_DATA_DIR"] = previous
                if previous_chroma is None:
                    os.environ.pop("NIRA_DISABLE_CHROMA", None)
                else:
                    os.environ["NIRA_DISABLE_CHROMA"] = previous_chroma

    logging.getLogger("nira_core").setLevel(logging.WARNING)
    checks: list[ValidationCheck] = []
    for package in ("fastapi", "uvicorn", "httpx", "yaml", "psutil"):
        checks.append(ValidationCheck(f"package:{package}", package_available(package), "available" if package_available(package) else "missing"))

    for path in (
        ROOT / "main.py",
        ROOT / "requirements.txt",
        ROOT / "nira_core" / "config" / "default.yaml",
        ROOT / "nira_core" / "api" / "static" / "index.html",
    ):
        checks.append(ValidationCheck(f"path:{path.name}", path.exists(), str(path)))

    try:
        runtime = build_runtime()
        logging.getLogger("nira_core").setLevel(logging.WARNING)
        manager = RuntimeStartupManager(runtime)
        startup_checks = await manager.validate()
        checks.extend(ValidationCheck(f"startup:{check.name}", check.ok or not check.required, check.details) for check in startup_checks)
        checks.append(ValidationCheck("runtime:models", bool(runtime.inference.models()), "model routes configured"))
        checks.append(ValidationCheck("runtime:capabilities", bool(runtime.capabilities.list()), "capabilities registered"))
        if full:
            checks.extend(await run_full_validation(runtime))
    except Exception as exc:
        checks.append(ValidationCheck("runtime:build", False, str(exc)))

    report = {"ok": all(check.ok for check in checks), "checks": [asdict(check) for check in checks]}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


async def run_full_validation(runtime) -> list[ValidationCheck]:
    """Simulate daily workloads without requiring live local models."""

    checks: list[ValidationCheck] = []
    runtime.inference._backends["ollama"] = ValidationBackend()
    try:
        coding = await runtime.workflows.run_coding("Validate coding workflow stability.")
        coding_cached = await runtime.workflows.run_coding("Validate coding workflow stability.")
        research = await runtime.workflows.run_research(
            "Validate research workflow.",
            seed_sources=[{"title": "Validation source", "url": "validation://source", "snippet": "Local validation content."}],
        )
        planner = await runtime.workflows.run_planner("Validate planning and memory update.")
        checks.append(ValidationCheck("full:workflows", all(item.answer for item in (coding, research, planner)), "coding/research/planner completed"))
        checks.append(
            ValidationCheck(
                "full:workflow_cache",
                bool(coding_cached.metadata.get("cache_hit")),
                json.dumps(coding_cached.metadata, default=str),
            )
        )
        analytics = runtime.workflow_learning.summary()
        checks.append(
            ValidationCheck(
                "full:workflow_analytics",
                bool(analytics["workflows"]) and analytics["cache"]["hits"] >= 1,
                json.dumps(analytics, default=str)[:500],
            )
        )
    except Exception as exc:
        checks.append(ValidationCheck("full:workflows", False, str(exc)))

    try:
        before = len(runtime.memory.timeline())
        runtime.memory.remember_task("dedupe", "same result", importance=0.5)
        runtime.memory.remember_task("dedupe", "same result", importance=0.5)
        after = len(runtime.memory.timeline())
        checks.append(ValidationCheck("full:memory_dedupe", after <= before + 1, f"before={before} after={after}"))
        health = runtime.memory.health()
        checks.append(ValidationCheck("full:memory_health", "fragmentation" in health, json.dumps(health, default=str)))
    except Exception as exc:
        checks.append(ValidationCheck("full:memory", False, str(exc)))

    try:
        queue = InMemoryTaskQueue("validation", max_depth=1)
        await queue.enqueue(TaskEnvelope(kind="one", payload={}))
        try:
            await queue.enqueue(TaskEnvelope(kind="two", payload={}))
            backpressure_ok = False
        except QueueBackpressureError:
            backpressure_ok = True
        checks.append(ValidationCheck("full:queue_backpressure", backpressure_ok, "queue rejects over-capacity tasks"))
    except Exception as exc:
        checks.append(ValidationCheck("full:queue_backpressure", False, str(exc)))

    try:
        calls = {"count": 0}

        async def flaky(task: TaskEnvelope) -> None:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("first attempt")

        queue = InMemoryTaskQueue("retry-validation", max_depth=4)
        pool = WorkerPool("retry-validation", queue, 1, flaky, runtime.telemetry, task_timeout_sec=2)
        await pool.start()
        await queue.enqueue(TaskEnvelope(kind="retry", payload={"retryable": True}, max_retries=1))
        for _ in range(50):
            if calls["count"] >= 2:
                break
            await asyncio.sleep(0.02)
        await pool.stop()
        checks.append(ValidationCheck("full:worker_retry", calls["count"] >= 2, f"calls={calls['count']}"))
    except Exception as exc:
        checks.append(ValidationCheck("full:worker_retry", False, str(exc)))

    try:
        runtime.inference._backends["ollama"] = FailingBackend()
        degraded = await runtime.orchestrator.run("Validate degraded inference.", task_type="classification")
        checks.append(ValidationCheck("full:degraded_inference", "unavailable" in degraded.text.lower(), degraded.text[:120]))
    except Exception as exc:
        checks.append(ValidationCheck("full:degraded_inference", False, str(exc)))

    try:
        runtime.inference._backends["ollama"] = ValidationBackend()
        before = runtime.telemetry.snapshot()["counters"].get("routing_decisions_total", 0)
        for index in range(12):
            await runtime.orchestrator.run(f"Health ping {index}", task_type="classification")
        state = runtime.state.snapshot()
        after = runtime.telemetry.snapshot()["counters"].get("routing_decisions_total", 0)
        checks.append(
            ValidationCheck(
                "full:long_session_stability",
                not state.get("active_tasks") and after >= before + 12,
                f"active_tasks={len(state.get('active_tasks', []))} routing_delta={after - before}",
            )
        )
    except Exception as exc:
        checks.append(ValidationCheck("full:long_session_stability", False, str(exc)))

    await runtime.event_bus.drain()
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate NIRA operational readiness")
    parser.add_argument("--full", action="store_true", help="Run simulated daily workload validation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(full=args.full))


if __name__ == "__main__":
    raise SystemExit(main())
