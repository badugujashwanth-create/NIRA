from __future__ import annotations

import time
from pathlib import Path

import pytest

from nira_core.config.settings import ModelSpec, NiraConfig, RuntimeConfig, ToolConfig, default_routing
from nira_core.inference import InferenceRequest
from nira_core.inference.base import result_from_text
from nira_core.inference.manager import LocalInferenceManager
from nira_core.sandbox import PermissionPolicy, SubprocessSandbox, ToolRequest
from nira_core.telemetry import Telemetry
from nira_core.tools.shell import ShellTool


class FakeBackend:
    def __init__(self) -> None:
        self.unloaded: list[str] = []

    async def generate(self, spec: ModelSpec, request: InferenceRequest):
        return result_from_text(f"{spec.alias}:{request.prompt[:12]}", spec, request.prompt, time.perf_counter())

    async def unload(self, spec: ModelSpec) -> None:
        self.unloaded.append(spec.alias)


@pytest.mark.asyncio
async def test_heavy_model_swap_policy(tmp_path: Path) -> None:
    backend = FakeBackend()
    config = NiraConfig(
        data_dir=tmp_path / "data",
        runtime=RuntimeConfig(),
        models={
            "a": ModelSpec(alias="a", name="heavy-a", heavy=True, provider="fake"),
            "b": ModelSpec(alias="b", name="heavy-b", heavy=True, provider="fake"),
        },
        routing={"coding": "a", "deep_reasoning": "b", **default_routing()},
    )
    manager = LocalInferenceManager(config, Telemetry(tmp_path / "telemetry"), backends={"fake": backend})
    await manager.generate(InferenceRequest(prompt="first", model_alias="a"))
    await manager.generate(InferenceRequest(prompt="second", model_alias="b"))
    assert manager.current_heavy_alias == "b"
    assert backend.unloaded == ["a"]


def test_permission_policy_denies_outside_workspace(tmp_path: Path) -> None:
    policy = PermissionPolicy(ToolConfig(workspace_root=tmp_path))
    decision = policy.decide(ToolRequest(tool_name="filesystem", action="read", path=Path("/tmp/outside.txt")))
    assert not decision.allowed
    assert decision.reason == "path_outside_workspace"


@pytest.mark.asyncio
async def test_shell_tool_requires_allowlisted_command(tmp_path: Path) -> None:
    config = ToolConfig(workspace_root=tmp_path, sandbox_root=tmp_path / "sandbox", allowed_commands=("python",))
    tool = ShellTool(PermissionPolicy(config), SubprocessSandbox(config), tmp_path)
    denied = await tool.run({"command": "powershell -Command Write-Output nope", "cwd": str(tmp_path)})
    assert not denied.ok
    assert "command_not_allowed" in denied.error
