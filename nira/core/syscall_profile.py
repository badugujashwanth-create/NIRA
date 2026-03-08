from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nira_agent.automation.models import ToolCall
from nira_agent.storage.sql_store import SQLStore


@dataclass(frozen=True)
class SyscallProjection:
    syscall_intensity: str
    kernel_transition_cost: str
    subsystem_involvement: list[str] = field(default_factory=list)
    estimated_syscalls: int = 0


@dataclass(frozen=True)
class CommandExecutionProfile:
    ts: str
    command_name: str
    duration_ms: float
    syscall_intensity: str
    kernel_transition_cost: str
    subsystem_involvement: list[str]
    ok: bool


class SyscallProfiler:
    def project(self, call: ToolCall) -> SyscallProjection:
        tool = call.tool.lower().strip()
        if tool in {"delete_file", "move_file", "write_file"}:
            return SyscallProjection(
                syscall_intensity="high",
                kernel_transition_cost="high",
                subsystem_involvement=["Object Manager", "I/O Manager", "Memory Manager"],
                estimated_syscalls=180,
            )
        if tool in {"open_app", "close_app"}:
            return SyscallProjection(
                syscall_intensity="medium",
                kernel_transition_cost="medium",
                subsystem_involvement=["Process Manager", "Object Manager", "Memory Manager"],
                estimated_syscalls=120,
            )
        if tool in {"read_file", "list_directory", "open_url"}:
            return SyscallProjection(
                syscall_intensity="low",
                kernel_transition_cost="low",
                subsystem_involvement=["I/O Manager", "Object Manager"],
                estimated_syscalls=60,
            )
        return SyscallProjection(
            syscall_intensity="medium",
            kernel_transition_cost="medium",
            subsystem_involvement=["Object Manager", "I/O Manager"],
            estimated_syscalls=90,
        )

    @staticmethod
    def begin() -> float:
        return time.perf_counter()

    def end(self, call: ToolCall, start_token: float, ok: bool, projection: SyscallProjection) -> CommandExecutionProfile:
        duration_ms = max(0.0, (time.perf_counter() - start_token) * 1000.0)
        return CommandExecutionProfile(
            ts=datetime.now(timezone.utc).isoformat(),
            command_name=call.tool,
            duration_ms=duration_ms,
            syscall_intensity=projection.syscall_intensity,
            kernel_transition_cost=projection.kernel_transition_cost,
            subsystem_involvement=projection.subsystem_involvement,
            ok=ok,
        )

    @staticmethod
    def persist(sql_store: SQLStore | None, profile: CommandExecutionProfile) -> None:
        if sql_store is None:
            return
        sql_store.insert_syscall_profile(
            ts=profile.ts,
            command_name=profile.command_name,
            duration_ms=profile.duration_ms,
            syscall_intensity=profile.syscall_intensity,
            kernel_transition_cost=profile.kernel_transition_cost,
            subsystems=profile.subsystem_involvement,
            ok=profile.ok,
        )
