from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from nira.config import ConfigLoader
from nira.core.agent_runtime import AgentRuntime
from nira.interface.interface_manager import InterfaceManager
from nira.security.tool_policy import ToolPermissionPolicy
from nira.tools.base import ToolAccess


NiraRuntime = AgentRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nira",
        description="NIRA local-first assistant with explicit tool permissions.",
    )
    parser.add_argument("--console", action="store_true", help="Use the console instead of the desktop window.")
    parser.add_argument(
        "--ui-audit-demo",
        action="store_true",
        help="Run a timed real-behavior desktop walkthrough for local screenshot verification.",
    )
    parser.add_argument(
        "--full-demo",
        action="store_true",
        help="Run the complete timed desktop walkthrough used for the release video.",
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--prompt", help="Run one request non-interactively and exit.")
    action.add_argument("--health", action="store_true", help="Print local runtime health as JSON and exit.")
    action.add_argument(
        "--inspect",
        nargs="?",
        const=".",
        metavar="PATH",
        help="Inspect a project path inside the workspace with the read-only analyzer.",
    )
    action.add_argument("--read-file", metavar="PATH", help="Read up to 64 KiB from a file inside the workspace.")
    parser.add_argument("--workspace", type=Path, help="Bound project tools to this existing directory.")
    parser.add_argument("--state-dir", type=Path, help="Store NIRA's local state in this directory.")
    parser.add_argument(
        "--enable-local-model",
        action="store_true",
        help="Enable the configured local llama.cpp endpoint. Disabled by default for fast offline behavior.",
    )
    parser.add_argument("--allow-write", action="store_true", help="Allow workspace-write tools for this process.")
    parser.add_argument("--allow-execute", action="store_true", help="Allow local process execution for this process.")
    parser.add_argument("--allow-network", action="store_true", help="Allow public-network tools for this process.")
    return parser


def build_runtime(args: argparse.Namespace | None = None) -> AgentRuntime:
    args = args or build_parser().parse_args([])
    config = ConfigLoader().load()
    if args.state_dir:
        config.base_dir = args.state_dir.expanduser().resolve()
        config.__post_init__()
    if args.enable_local_model:
        config.local_model_enabled = True

    policy = ToolPermissionPolicy()
    grants: list[ToolAccess] = []
    if args.allow_write:
        grants.append(ToolAccess.WORKSPACE_WRITE)
    if args.allow_execute:
        grants.append(ToolAccess.PROCESS)
    if args.allow_network:
        grants.append(ToolAccess.NETWORK)
    policy.grant(*grants)
    return AgentRuntime(config=config, permission_policy=policy)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.ui_audit_demo and args.full_demo:
        raise SystemExit("Choose either --ui-audit-demo or --full-demo, not both.")
    original_cwd = Path.cwd()
    runtime: AgentRuntime | None = None
    try:
        if args.workspace:
            workspace = args.workspace.expanduser().resolve()
            if not workspace.is_dir():
                raise SystemExit(f"Workspace does not exist or is not a directory: {workspace}")
            os.chdir(workspace)

        runtime = build_runtime(args)
        if args.health:
            print(json.dumps(runtime.health(), indent=2, sort_keys=True))
            return 0
        if args.inspect is not None:
            result = runtime.inspect_project(args.inspect)
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.ok else 2
        if args.read_file is not None:
            result = runtime.read_workspace_file(args.read_file)
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0 if result.ok else 2
        if args.prompt is not None:
            response = runtime.handle(args.prompt)
            print(response.text)
            return 0 if all(bool(item.get("ok")) for item in response.task_results) else 2

        manager = InterfaceManager(runtime, prefer_gui=not args.console)
        if args.console:
            runtime.set_approval_callback(_console_approval)
        manager.run(demo_mode=args.ui_audit_demo, full_demo=args.full_demo)
        return 0
    finally:
        if runtime is not None:
            runtime.shutdown()
        os.chdir(original_cwd)


def _console_approval(tool_name: str, args: dict[str, Any], access: ToolAccess) -> bool:
    visible = {
        key: value
        for key, value in args.items()
        if key in {"action", "path", "cwd", "command", "source", "destination", "query"}
    }
    print(f"\nPermission required: {access.value} via {tool_name}")
    if visible:
        print(f"Requested arguments: {json.dumps(visible, ensure_ascii=True)}")
    answer = input("Approve this action once? [y/N] ").strip().lower()
    return answer in {"y", "yes"}


if __name__ == "__main__":
    raise SystemExit(main())
