from __future__ import annotations

from pathlib import Path

from nira_core.config import load_config
from nira_core.routing import TaskRouter
from nira_core.telemetry import Telemetry


def test_load_default_config_uses_nira_core_config() -> None:
    config = load_config()
    assert config.runtime.default_context_window == 512
    assert config.runtime.max_final_context_tokens == 400
    assert "primary_coding" in config.models
    assert config.routing["coding"] == "primary_coding"


def test_router_routes_coding_to_primary_model(tmp_path: Path) -> None:
    config = load_config()
    router = TaskRouter(config, Telemetry(tmp_path / "telemetry"))
    decision = router.route("write Python tests for the retrieval pipeline")
    assert decision.task_type == "coding"
    assert decision.model_alias == "primary_coding"
