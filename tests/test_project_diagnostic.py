from __future__ import annotations

from pathlib import Path

from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime


def _project(root: Path) -> Path:
    project = root / "sample"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
    (project / "app.py").write_text("# TODO: cover the fallback\nprint('ok')\n", encoding="utf-8")
    return project


def test_diagnostic_stops_at_permission_and_can_retry(tmp_path: Path) -> None:
    runtime = AgentRuntime(NiraConfig(base_dir=tmp_path / "state"))
    runtime.select_workspace(_project(tmp_path))

    denied = runtime.run_project_diagnostic("TODO")

    assert denied.ok is False
    assert denied.recoverable is True
    assert denied.permission["reason"] == "process_approval_required"
    assert denied.diagnostic["data"]["permission_required"] is True

    runtime.set_approval_callback(lambda _name, _args, _access: True)
    verified = runtime.retry_project_diagnostic("TODO")

    assert verified.ok is True
    assert verified.search["data"]["match_count"] == 1
    assert verified.verification["verified"] is True
    assert verified.permission["reason"] == "approved_once"
    assert runtime.search_conversations("diagnostic verified")
    runtime.shutdown()


def test_diagnostic_honors_cancellation_before_next_tool(tmp_path: Path) -> None:
    runtime = AgentRuntime(NiraConfig(base_dir=tmp_path / "state"))
    runtime.select_workspace(_project(tmp_path))
    runtime._diagnostic_cancel_event.set()

    report = runtime.project_diagnostic_workflow.run(
        workspace=str(runtime.health()["workspace"]),
        query="TODO",
        profile="python_compile",
        state=type("State", (), {"context": {"cwd": str(runtime.health()["workspace"])}})(),
        cancel_event=runtime._diagnostic_cancel_event,
    )

    assert report.cancelled is True
    assert report.timeline[0].stage == "cancelled"
    runtime.shutdown()
