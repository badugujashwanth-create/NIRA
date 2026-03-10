from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _parse_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class Settings:
    app_name: str = "NIRA"
    environment: str = "development"
    log_level: str = "INFO"
    project_root: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])
    data_dir: Path = field(default_factory=lambda: Path("data"))
    cache_dir: Path = field(default_factory=lambda: Path("data") / "cache")
    knowledge_path: Path = field(default_factory=lambda: Path("data") / "knowledge_base.json")
    max_research_results: int = 5
    max_plan_steps: int = 6
    background_workers: int = 4

    def __post_init__(self) -> None:
        self.project_root = self.project_root.expanduser().resolve()
        self.data_dir = self._resolve(self.data_dir)
        self.cache_dir = self._resolve(self.cache_dir)
        self.knowledge_path = self._resolve(self.knowledge_path)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser()
        if candidate.is_absolute():
            return candidate
        return self.project_root / candidate


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("NIRA_APP_NAME", "NIRA"),
        environment=os.getenv("NIRA_ENVIRONMENT", "development"),
        log_level=os.getenv("NIRA_LOG_LEVEL", "INFO"),
        max_research_results=_parse_int(os.getenv("NIRA_MAX_RESEARCH_RESULTS"), 5),
        max_plan_steps=_parse_int(os.getenv("NIRA_MAX_PLAN_STEPS"), 6),
        background_workers=_parse_int(os.getenv("NIRA_BACKGROUND_WORKERS"), 4),
    )
