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
class NiraConfig:
    base_dir: Path = field(default_factory=lambda: Path.home() / ".nira")
    llama_base_url: str = "http://127.0.0.1:8080"
    llama_model: str | None = None
    planner_model: str | None = None
    coding_model: str | None = None
    fast_model: str | None = None
    research_model: str | None = None
    embedding_model: str | None = None
    model_overrides_json: str = ""
    llama_timeout_sec: int = 15
    manage_llama_server: bool = False
    llama_dir: str | None = None
    llama_model_path: str | None = None
    web_research_enabled: bool = False
    max_short_term_turns: int = 18
    max_vector_hits: int = 5
    workflow_detection_threshold: int = 2
    build_timeout_sec: int = 180
    enable_voice: bool = False
    enable_overlay: bool = False
    enable_notifications: bool = True
    startup_timeout_sec: int = 120
    model_max_tokens: int = 512
    max_context_chars: int = 4800
    max_cached_models: int = 3
    model_idle_ttl_sec: int = 900

    database_path: Path = field(init=False)
    logs_dir: Path = field(init=False)
    documents_dir: Path = field(init=False)
    research_dir: Path = field(init=False)
    training_dir: Path = field(init=False)
    artifacts_dir: Path = field(init=False)
    vector_store_path: Path = field(init=False)
    workflow_store_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.base_dir = Path(self.base_dir).expanduser()
        self.database_path = self.base_dir / "runtime.db"
        self.logs_dir = self.base_dir / "logs"
        self.documents_dir = self.base_dir / "documents"
        self.research_dir = self.base_dir / "research"
        self.training_dir = self.base_dir / "training"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.vector_store_path = self.base_dir / "vector_store.json"
        self.workflow_store_path = self.base_dir / "workflows.json"
        self.ensure_directories()

    @property
    def local_llm_base_url(self) -> str:
        return self.llama_base_url

    @property
    def local_llm_model(self) -> str | None:
        return self.llama_model

    @property
    def local_llm_timeout_sec(self) -> int:
        return self.llama_timeout_sec

    def ensure_directories(self) -> None:
        for path in (
            self.base_dir,
            self.logs_dir,
            self.documents_dir,
            self.research_dir,
            self.training_dir,
            self.artifacts_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


AgentConfig = NiraConfig


class ConfigLoader:
    def __init__(self, path: Path | None = None) -> None:
        base_dir = Path.home() / ".nira"
        self.path = path or (base_dir / "config.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> NiraConfig:
        user = self._read_user()
        cfg = NiraConfig()
        for key, default_value in cfg.__dict__.items():
            if key in {
                "database_path",
                "logs_dir",
                "documents_dir",
                "research_dir",
                "training_dir",
                "artifacts_dir",
                "vector_store_path",
                "workflow_store_path",
            }:
                continue
            env_key = f"NIRA_{key.upper()}"
            value = os.getenv(env_key, user.get(key, default_value))
            setattr(cfg, key, self._coerce(default_value, value))
        cfg.__post_init__()
        return cfg

    def _read_user(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.path.with_suffix(f"{self.path.suffix}.invalid.bak")
            try:
                backup.write_text(self.path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            except OSError:
                return {}
            return {}
        except OSError:
            return {}

    def _coerce(self, default: Any, value: Any) -> Any:
        if isinstance(default, bool):
            return _parse_bool(value, default)
        if isinstance(default, int):
            return _parse_int(value, default)
        if isinstance(default, Path):
            return Path(value)
        return value if value is not None else default
