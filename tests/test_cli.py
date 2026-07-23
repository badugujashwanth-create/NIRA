from __future__ import annotations

import json

from nira.main import build_parser, main


def test_health_command_reports_offline_safe_defaults(tmp_path, capsys) -> None:
    exit_code = main(["--health", "--state-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["mode"] == "deterministic-offline"
    assert payload["allowed_access"] == ["read", "state"]
    assert payload["interaction_logging_enabled"] is False


def test_inspect_and_read_file_commands_are_bounded_to_workspace(tmp_path, capsys) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (workspace / "hello.py").write_text("print('hello')\n", encoding="utf-8")

    inspect_code = main(
        ["--inspect", ".", "--workspace", str(workspace), "--state-dir", str(tmp_path / "state")]
    )
    inspected = json.loads(capsys.readouterr().out)
    assert inspect_code == 0
    assert inspected["ok"] is True
    assert inspected["data"]["python_files"] == 1

    read_code = main(
        ["--read-file", "hello.py", "--workspace", str(workspace), "--state-dir", str(tmp_path / "state")]
    )
    read = json.loads(capsys.readouterr().out)
    assert read_code == 0
    assert read["ok"] is True
    assert "print('hello')" in read["output"]


def test_read_file_rejects_path_escape(tmp_path, capsys) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")

    exit_code = main(
        ["--read-file", "../outside.txt", "--workspace", str(workspace), "--state-dir", str(tmp_path / "state")]
    )
    result = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert result["ok"] is False
    assert "escapes allowed root" in result["output"]


def test_full_demo_flag_is_explicit() -> None:
    args = build_parser().parse_args(["--full-demo"])
    assert args.full_demo is True
    assert args.ui_audit_demo is False


def test_status_command_reports_integrated_product_snapshot(tmp_path, capsys) -> None:
    exit_code = main(["--status", "--state-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["mode"] == "deterministic-offline"
    assert payload["memory"]["storage"] == "Local SQLite"
    assert payload["workflows"]["template_count"] >= 1
    assert payload["tools"]["count"] >= 1
    assert any(agent["name"] == "Safety" for agent in payload["agents"])


def test_search_and_diagnostic_commands_use_bounded_workflow(tmp_path, capsys) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (workspace / "hello.py").write_text("# TODO: add a test\nprint('hello')\n", encoding="utf-8")
    state = tmp_path / "state"

    search_code = main(
        ["--search", "TODO", "--workspace", str(workspace), "--state-dir", str(state)]
    )
    searched = json.loads(capsys.readouterr().out)
    assert search_code == 0
    assert searched["data"]["match_count"] == 1

    diagnostic_code = main(
        [
            "--diagnose",
            "TODO",
            "--workspace",
            str(workspace),
            "--state-dir",
            str(state),
            "--allow-execute",
        ]
    )
    diagnosed = json.loads(capsys.readouterr().out)
    assert diagnostic_code == 0
    assert diagnosed["verification"]["verified"] is True
    assert diagnosed["permission"]["reason"] == "allowed_by_policy"
