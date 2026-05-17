from __future__ import annotations

import argparse
import asyncio
import json
import logging

from nira_core.bootstrap import build_runtime


def parse_args() -> argparse.Namespace:
    """Parse CLI commands for the local-first runtime."""

    parser = argparse.ArgumentParser(description="NIRA Mini local-first cognitive infrastructure")
    parser.add_argument("--config", default=None, help="Path to a YAML config file")
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="Launch the FastAPI API server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)

    start = subparsers.add_parser("start", help="Validate, initialize, and launch the usable NIRA runtime")
    start.add_argument("--host", default="127.0.0.1")
    start.add_argument("--port", type=int, default=8787)

    run = subparsers.add_parser("run", help="Run one orchestrated task")
    run.add_argument("task")
    run.add_argument("--task-type", default=None)

    subparsers.add_parser("demo", help="Run deterministic showcase workflows")
    subparsers.add_parser("models", help="Print configured model routes")
    subparsers.add_parser("telemetry", help="Print local telemetry snapshot")
    return parser.parse_args()


async def run_once(task: str, task_type: str | None, config_path: str | None) -> int:
    """Execute one task through the cognitive orchestrator."""

    runtime = build_runtime(config_path)
    result = await runtime.orchestrator.run(task, task_type=task_type)
    print(result.text)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "serve":
        import uvicorn

        from nira_core.api import create_app

        runtime = build_runtime(args.config)
        uvicorn.run(create_app(runtime), host=args.host, port=args.port)
        return 0
    if args.command == "start":
        import uvicorn

        from nira_core.api import create_app
        from nira_core.runtime import RuntimeStartupManager

        runtime = build_runtime(args.config)
        manager = RuntimeStartupManager(runtime, host=args.host, port=args.port)
        report = asyncio.run(manager.start())
        _print_startup_report(report.to_dict())
        try:
            uvicorn.run(create_app(runtime), host=args.host, port=args.port)
        finally:
            asyncio.run(manager.stop())
        return 0
    if args.command == "run":
        return asyncio.run(run_once(args.task, args.task_type, args.config))
    if args.command == "demo":
        from nira_core.runtime import print_demo, run_demo

        runtime = build_runtime(args.config)
        logging.getLogger("nira_core").setLevel(logging.WARNING)
        print_demo(asyncio.run(run_demo(runtime)))
        return 0
    if args.command == "models":
        runtime = build_runtime(args.config)
        print(json.dumps(runtime.inference.models(), indent=2))
        return 0
    if args.command == "telemetry":
        runtime = build_runtime(args.config)
        print(json.dumps(runtime.telemetry.snapshot(), indent=2, default=str))
        return 0
    print("Use one of: start, serve, run, demo, models, telemetry")
    return 2


def _print_startup_report(report: dict[str, object]) -> None:
    print("NIRA startup summary")
    print(f"UI:  {report['ui_url']}")
    print(f"API: {report['api_url']}")
    for check in report["checks"]:
        mark = "ok" if check["ok"] else ("warn" if not check["required"] else "fail")
        print(f"[{mark}] {check['name']}: {check['details']}")


if __name__ == "__main__":
    raise SystemExit(main())
