from __future__ import annotations

import json

from nira.main import main


def test_health_command_reports_offline_safe_defaults(tmp_path, capsys) -> None:
    exit_code = main(["--health", "--state-dir", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ready"
    assert payload["mode"] == "deterministic-offline"
    assert payload["allowed_access"] == ["read", "state"]
    assert payload["interaction_logging_enabled"] is False
