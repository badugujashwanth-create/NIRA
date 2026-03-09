from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from nira.config import NiraConfig


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    model_name: str
    base_url: str
    timeout_sec: int
    manage_server: bool = False
    llama_dir: str | None = None
    model_path: str | None = None
    startup_timeout_sec: int = 120
    max_tokens: int = 512
    capabilities: list[str] = field(default_factory=list)
    embedding: bool = False


class ModelRegistry:
    def __init__(self, specs: dict[str, ModelSpec]) -> None:
        self._specs = dict(specs)

    @classmethod
    def from_config(cls, config: NiraConfig) -> "ModelRegistry":
        default_model = config.llama_model or "llama.cpp-default"
        planner_model = config.planner_model or default_model
        coding_model = config.coding_model or planner_model
        fast_model = config.fast_model or default_model
        research_model = config.research_model or planner_model
        embedding_model = config.embedding_model or fast_model

        specs = {
            "planner_model": ModelSpec(
                alias="planner_model",
                model_name=planner_model,
                base_url=config.llama_base_url,
                timeout_sec=config.llama_timeout_sec,
                manage_server=config.manage_llama_server,
                llama_dir=config.llama_dir,
                model_path=config.llama_model_path,
                startup_timeout_sec=config.startup_timeout_sec,
                max_tokens=max(config.model_max_tokens, 768),
                capabilities=["planning", "reasoning"],
            ),
            "coding_model": ModelSpec(
                alias="coding_model",
                model_name=coding_model,
                base_url=config.llama_base_url,
                timeout_sec=config.llama_timeout_sec,
                manage_server=config.manage_llama_server,
                llama_dir=config.llama_dir,
                model_path=config.llama_model_path,
                startup_timeout_sec=config.startup_timeout_sec,
                max_tokens=max(config.model_max_tokens, 768),
                capabilities=["coding", "implementation"],
            ),
            "fast_model": ModelSpec(
                alias="fast_model",
                model_name=fast_model,
                base_url=config.llama_base_url,
                timeout_sec=config.llama_timeout_sec,
                manage_server=config.manage_llama_server,
                llama_dir=config.llama_dir,
                model_path=config.llama_model_path,
                startup_timeout_sec=config.startup_timeout_sec,
                max_tokens=config.model_max_tokens,
                capabilities=["quick", "chat", "emotion"],
            ),
            "research_model": ModelSpec(
                alias="research_model",
                model_name=research_model,
                base_url=config.llama_base_url,
                timeout_sec=config.llama_timeout_sec,
                manage_server=config.manage_llama_server,
                llama_dir=config.llama_dir,
                model_path=config.llama_model_path,
                startup_timeout_sec=config.startup_timeout_sec,
                max_tokens=max(config.model_max_tokens, 896),
                capabilities=["research", "analysis"],
            ),
            "embedding_model": ModelSpec(
                alias="embedding_model",
                model_name=embedding_model,
                base_url=config.llama_base_url,
                timeout_sec=config.llama_timeout_sec,
                manage_server=config.manage_llama_server,
                llama_dir=config.llama_dir,
                model_path=config.llama_model_path,
                startup_timeout_sec=config.startup_timeout_sec,
                max_tokens=256,
                capabilities=["embedding", "retrieval"],
                embedding=True,
            ),
        }
        overrides = cls._parse_overrides(config.model_overrides_json)
        for alias, values in overrides.items():
            if alias not in specs:
                continue
            specs[alias] = cls._merge_spec(specs[alias], values)
        return cls(specs)

    def get(self, alias: str) -> ModelSpec:
        if alias in self._specs:
            return self._specs[alias]
        return self._specs["fast_model"]

    def has(self, alias: str) -> bool:
        return alias in self._specs

    def aliases(self) -> list[str]:
        return sorted(self._specs.keys())

    def to_mapping(self) -> dict[str, str]:
        return {alias: spec.model_name for alias, spec in self._specs.items()}

    @staticmethod
    def _parse_overrides(raw: str) -> dict[str, dict[str, Any]]:
        body = raw.strip()
        if not body:
            return {}
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return {
            str(alias): value
            for alias, value in parsed.items()
            if isinstance(alias, str) and isinstance(value, dict)
        }

    @staticmethod
    def _merge_spec(spec: ModelSpec, values: dict[str, Any]) -> ModelSpec:
        payload = {
            "alias": spec.alias,
            "model_name": str(values.get("model", values.get("model_name", spec.model_name))),
            "base_url": str(values.get("base_url", spec.base_url)),
            "timeout_sec": int(values.get("timeout_sec", spec.timeout_sec)),
            "manage_server": bool(values.get("manage_server", spec.manage_server)),
            "llama_dir": values.get("llama_dir", spec.llama_dir),
            "model_path": values.get("model_path", spec.model_path),
            "startup_timeout_sec": int(values.get("startup_timeout_sec", spec.startup_timeout_sec)),
            "max_tokens": int(values.get("max_tokens", spec.max_tokens)),
            "capabilities": list(values.get("capabilities", spec.capabilities)),
            "embedding": bool(values.get("embedding", spec.embedding)),
        }
        return ModelSpec(**payload)
