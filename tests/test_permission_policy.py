from __future__ import annotations

import tempfile
from pathlib import Path

from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime
from nira.security.tool_policy import ToolPermissionPolicy
from nira.tools import Tool, ToolAccess, ToolRegistry, ToolResult
from nira.models.llama_runtime import ModelResponse


class WriteTool(Tool):
    name = "write_test"
    description = "Test-only side effect"
    access = ToolAccess.WORKSPACE_WRITE

    def __init__(self) -> None:
        self.calls = 0

    def run(self, args, state) -> ToolResult:
        self.calls += 1
        return ToolResult(True, "wrote")


class FakeModel:
    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text="local test response", provider="test")

    def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]

    def close(self) -> None:
        return None


def test_workspace_write_is_blocked_by_default() -> None:
    registry = ToolRegistry()
    tool = WriteTool()
    registry.register(tool)

    result = registry.execute(tool.name, {}, object())

    assert not result.ok
    assert result.data["permission_required"] is True
    assert result.data["access"] == "workspace_write"
    assert tool.calls == 0


def test_callback_can_approve_one_action() -> None:
    approvals: list[tuple[str, ToolAccess]] = []
    policy = ToolPermissionPolicy(
        approval_callback=lambda name, _args, access: approvals.append((name, access)) is None
    )
    registry = ToolRegistry(permission_policy=policy)
    tool = WriteTool()
    registry.register(tool)

    result = registry.execute(tool.name, {"path": "note.txt"}, object())

    assert result.ok
    assert approvals == [("write_test", ToolAccess.WORKSPACE_WRITE)]
    assert tool.calls == 1


def test_chat_does_not_create_notes_or_require_tool_permission() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = NiraConfig(base_dir=Path(tmp))
        runtime = AgentRuntime(config=config, model=FakeModel())

        response = runtime.handle("Hello NIRA")

        assert response.text
        assert response.task_results == []
        assert not (config.documents_dir / "chat_notes.md").exists()
        assert not (config.training_dir / "interactions.jsonl").exists()
        runtime.shutdown()


def test_permission_decisions_are_bounded_and_exclude_tool_arguments() -> None:
    policy = ToolPermissionPolicy()
    for index in range(120):
        policy.authorize("write_test", {"secret": f"token-{index}"}, ToolAccess.WORKSPACE_WRITE)

    decisions = policy.recent_decisions(limit=100)
    assert len(decisions) == 100
    assert decisions[-1]["allowed"] is False
    assert decisions[-1]["reason"] == "workspace_write_approval_required"
    assert "token" not in str(decisions)


def test_failed_approval_callback_defaults_to_denied() -> None:
    def fail_callback(_name, _args, _access):
        raise RuntimeError("UI unavailable")

    policy = ToolPermissionPolicy(approval_callback=fail_callback)
    allowed, reason = policy.authorize("write_test", {}, ToolAccess.WORKSPACE_WRITE)

    assert allowed is False
    assert reason == "approval_callback_failed"


def test_denied_process_is_not_retried_as_a_repair() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        approvals: list[tuple[str, ToolAccess]] = []
        runtime = AgentRuntime(config=NiraConfig(base_dir=Path(tmp)), model=FakeModel())
        runtime.set_approval_callback(
            lambda name, _args, access: approvals.append((name, access)) is not None
        )

        response = runtime.handle("add authentication to this repo")

        assert approvals == [("run_build", ToolAccess.PROCESS)]
        assert response.task_results[-1]["data"]["permission_required"] is True
        assert "Blocked 'run_build'" in response.text
        runtime.shutdown()
