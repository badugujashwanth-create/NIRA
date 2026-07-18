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
