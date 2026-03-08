from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class AgentConfig:
    local_llm_base_url: str = "http://127.0.0.1:8080"
    local_llm_timeout_sec: int = 420
    local_llm_model: str | None = None
    cloud_fallback_enabled: bool = False
    cloud_endpoint: str | None = None
    cloud_api_key: str | None = None
    cloud_timeout_sec: int = 45
    escalation_threshold: float = 0.42
    manual_cloud_escalation_only: bool = True
    route_cache_ttl_sec: int = 300
    route_cache_max_items: int = 512
    permission_default: str = "standard"
    passphrase_required: bool = True
    passphrase_env: str = "NIRA_PASSPHRASE"
    encrypt_key_env: str = "NIRA_ENCRYPTION_KEY"
    max_context_chars: int = 12000
    max_history_turns: int = 14
    compress_every_n_turns: int = 6
    memory_compress_token_threshold: int = 900
    proactive_cooldown_sec: int = 300
    proactive_enabled: bool = True
    inference_cooldown_ms: int = 250
    cpu_throttle_ms: int = 40
    llm_route_timeout_sec: int = 420
    route_context_chars: int = 320
    clarification_threshold: float = 0.33
    max_tool_replans: int = 1
    monitor_interval_sec: int = 5
    skills_dir: str = "skills"
    dsl_workflow_file: str = "workflows.dsl"
    sql_enabled: bool = True
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "nira_agent"
    distraction_apps: list[str] = field(default_factory=lambda: ["chrome.exe", "msedge.exe", "firefox.exe"])

    def ensure_directories(self) -> None:
        storage = Path.home() / ".nira_agent"
        (storage / "logs").mkdir(parents=True, exist_ok=True)
        (storage / "memory").mkdir(parents=True, exist_ok=True)
        (storage / "security").mkdir(parents=True, exist_ok=True)

    def db_settings(self) -> dict[str, object]:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
        }


class ConfigLoader:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (Path.home() / ".nira_agent" / "config.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> AgentConfig:
        user = self._read_user()
        cfg = AgentConfig()
        env_map = {
            "db_host": "DB_HOST",
            "db_port": "DB_PORT",
            "db_user": "DB_USER",
            "db_password": "DB_PASSWORD",
            "db_name": "DB_NAME",
        }
        for key, default_value in cfg.__dict__.items():
            env_key = env_map.get(key, f"NIRA_{key.upper()}")
            value = os.getenv(env_key, user.get(key, default_value))
            setattr(cfg, key, self._coerce(default_value, value))
        cfg.ensure_directories()
        return cfg

    def _read_user(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _coerce(self, default: Any, value: Any) -> Any:
        if isinstance(default, bool):
            return _parse_bool(value, default)
        if isinstance(default, int):
            return _parse_int(value, default)
        if isinstance(default, float):
            try:
                return float(value)
            except (TypeError, ValueError):
                return default
        if isinstance(default, list):
            if isinstance(value, list):
                return value
            if not value:
                return default
            return [x.strip() for x in str(value).split(",") if x.strip()]
        return value if value is not None else default
