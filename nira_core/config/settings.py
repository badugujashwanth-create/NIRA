from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Runtime guardrails for CPU-only constrained inference."""

    ram_limit_mb: int = 12_000
    cpu_only: bool = True
    default_context_window: int = 512
    max_final_context_tokens: int = 400
    ollama_base_url: str = "http://127.0.0.1:11434"
    llama_cpp_base_url: str = "http://127.0.0.1:8080"
    inference_timeout_sec: float = 180.0


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """A model route target with enough metadata for safe swapping."""

    alias: str
    name: str
    provider: str = "ollama"
    role: str = "general"
    quantization: str = "q4_k_m"
    context_window: int = 512
    heavy: bool = False
    keep_alive: str = "0s"
    temperature: float = 0.2
    num_predict: int = 256


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    """Async worker pool limits tuned for CPU-only laptops."""

    redis_url: str = "redis://127.0.0.1:6379/0"
    inference_concurrency: int = 1
    retrieval_concurrency: int = 4
    browser_concurrency: int = 2
    compression_concurrency: int = 1
    queue_timeout_sec: float = 30.0
    task_timeout_sec: float = 120.0
    queue_max_depth: int = 128


@dataclass(frozen=True, slots=True)
class MemoryPolicyConfig:
    """Bounded memory settings to prevent unbounded local growth."""

    working_max_items: int = 128
    working_ttl_sec: int = 3_600
    episodic_ttl_days: int = 30
    archive_after_days: int = 14
    semantic_top_k: int = 8
    decay_half_life_days: float = 14.0
    min_importance: float = 0.05


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Sandbox and allowlist settings for local tool execution."""

    workspace_root: Path = field(default_factory=lambda: Path.cwd())
    sandbox_root: Path = field(default_factory=lambda: Path.cwd() / ".nira_sandbox")
    docker_enabled: bool = False
    command_timeout_sec: float = 30.0
    allowed_commands: tuple[str, ...] = (
        "python",
        "python3",
        "pytest",
        "git",
        "rg",
        "ls",
        "cat",
        "pwd",
    )


@dataclass(frozen=True, slots=True)
class NiraConfig:
    """Top-level runtime configuration for all local-first layers."""

    base_dir: Path = field(default_factory=lambda: Path.cwd())
    data_dir: Path = field(default_factory=lambda: Path.cwd() / ".nira_data")
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    workers: WorkerConfig = field(default_factory=WorkerConfig)
    memory: MemoryPolicyConfig = field(default_factory=MemoryPolicyConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    models: dict[str, ModelSpec] = field(default_factory=dict)
    routing: dict[str, str] = field(default_factory=dict)

    def model_for_alias(self, alias: str) -> ModelSpec:
        """Return a model spec or raise a descriptive configuration error."""

        try:
            return self.models[alias]
        except KeyError as exc:
            raise KeyError(f"Unknown model alias: {alias}") from exc


def default_models() -> dict[str, ModelSpec]:
    """Return the default CPU-safe model stack."""

    return {
        "primary_coding": ModelSpec(
            alias="primary_coding",
            name="qwen2.5-coder:7b-gguf-q4_k_m",
            role="coding",
            heavy=True,
            num_predict=384,
        ),
        "fast": ModelSpec(
            alias="fast",
            name="phi:3",
            role="classification",
            heavy=False,
            num_predict=160,
        ),
        "compression": ModelSpec(
            alias="compression",
            name="phi:3",
            role="compression",
            heavy=False,
            num_predict=220,
        ),
        "future_reasoning": ModelSpec(
            alias="future_reasoning",
            name="qwen2.5:14b-gguf-q4_k_m",
            role="deep_reasoning",
            heavy=True,
            num_predict=512,
        ),
    }


def default_routing() -> dict[str, str]:
    """Return route names mapped to model aliases."""

    return {
        "coding": "primary_coding",
        "classification": "fast",
        "compression": "compression",
        "retrieval": "fast",
        "deep_reasoning": "future_reasoning",
        "general": "fast",
    }


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        item = line.strip()
        if not item or item.startswith("#") or "=" not in item:
            continue
        key, value = item.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("YAML config requires PyYAML. Install with: pip install -r requirements.txt") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return data


def _models_from_mapping(mapping: dict[str, Any]) -> dict[str, ModelSpec]:
    models = default_models()
    for alias, values in mapping.items():
        if not isinstance(values, dict):
            raise ValueError(f"Model config for {alias} must be a mapping")
        existing = models.get(alias)
        if existing:
            models[alias] = replace(existing, **values)
        else:
            models[alias] = ModelSpec(alias=alias, **values)
    return models


def load_config(config_path: str | Path | None = None, env_path: str | Path | None = None) -> NiraConfig:
    """Load .env and YAML configuration, applying conservative defaults first."""

    base_dir = Path.cwd()
    _load_dotenv(Path(env_path) if env_path else base_dir / ".env")
    yaml_path = Path(config_path) if config_path else base_dir / "nira_core" / "config" / "default.yaml"
    raw = _read_yaml(yaml_path)

    runtime_raw = raw.get("runtime", {})
    worker_raw = raw.get("workers", {})
    memory_raw = raw.get("memory", {})
    tool_raw = raw.get("tools", {})

    runtime = RuntimeConfig(
        ram_limit_mb=_env_int("NIRA_RAM_LIMIT_MB", int(runtime_raw.get("ram_limit_mb", 12_000))),
        cpu_only=_env_bool("NIRA_CPU_ONLY", bool(runtime_raw.get("cpu_only", True))),
        default_context_window=_env_int(
            "NIRA_CONTEXT_WINDOW", int(runtime_raw.get("default_context_window", 512))
        ),
        max_final_context_tokens=_env_int(
            "NIRA_MAX_FINAL_CONTEXT_TOKENS", int(runtime_raw.get("max_final_context_tokens", 400))
        ),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", runtime_raw.get("ollama_base_url", "http://127.0.0.1:11434")),
        llama_cpp_base_url=os.getenv(
            "LLAMA_CPP_BASE_URL", runtime_raw.get("llama_cpp_base_url", "http://127.0.0.1:8080")
        ),
        inference_timeout_sec=float(runtime_raw.get("inference_timeout_sec", 180.0)),
    )

    workers = WorkerConfig(**worker_raw)
    memory = MemoryPolicyConfig(**memory_raw)
    tool_paths = dict(tool_raw)
    if "workspace_root" in tool_paths:
        tool_paths["workspace_root"] = Path(tool_paths["workspace_root"])
    if "sandbox_root" in tool_paths:
        tool_paths["sandbox_root"] = Path(tool_paths["sandbox_root"])
    tools = ToolConfig(**tool_paths)
    models = _models_from_mapping(raw.get("models", {}))
    routing = _deep_merge(default_routing(), raw.get("routing", {}))

    data_dir = Path(os.getenv("NIRA_DATA_DIR", raw.get("data_dir", str(base_dir / ".nira_data"))))
    return NiraConfig(
        base_dir=base_dir,
        data_dir=data_dir,
        runtime=runtime,
        workers=workers,
        memory=memory,
        tools=tools,
        models=models,
        routing=routing,
    )
