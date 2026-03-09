from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from nira.models.llama_runtime import LocalModel, ModelResponse
from nira.models.model_registry import ModelRegistry, ModelSpec

ModelFactory = Callable[[ModelSpec], Any]


@dataclass
class ManagedModelHandle:
    model: Any
    last_used: float
    external: bool = False


class ModelManager:
    def __init__(
        self,
        registry: ModelRegistry,
        *,
        performance_analyzer=None,
        max_cached_models: int = 3,
        idle_ttl_sec: int = 900,
        default_model: Any | None = None,
        model_factory: ModelFactory | None = None,
    ) -> None:
        self.registry = registry
        self.performance_analyzer = performance_analyzer
        self.max_cached_models = max(1, max_cached_models)
        self.idle_ttl_sec = max(30, idle_ttl_sec)
        self.default_model = default_model
        self.model_factory = model_factory or self._build_local_model
        self._loaded: dict[str, ManagedModelHandle] = {}
        self._last_generation_ms = 0.0
        self._last_embedding_ms = 0.0

    def load_model(self, model_name: str):
        self.unload_unused_models()
        handle = self._loaded.get(model_name)
        if handle is not None:
            handle.last_used = time.time()
            return handle.model

        if self.default_model is not None:
            model = self.default_model
            external = True
        else:
            spec = self.registry.get(model_name)
            model = self.model_factory(spec)
            external = False
        self._loaded[model_name] = ManagedModelHandle(model=model, last_used=time.time(), external=external)
        self._trim_cache()
        return model

    def generate(self, model_name: str, prompt: str) -> ModelResponse:
        started = time.perf_counter()
        model = self.load_model(model_name)
        try:
            result = model.generate(prompt)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            self._last_generation_ms = duration_ms
            self._record_metric(f"model.generate.{model_name}", duration_ms, False)
            return ModelResponse(text="", provider=model_name, raw={"error": str(exc)})
        duration_ms = (time.perf_counter() - started) * 1000
        self._last_generation_ms = duration_ms
        self._record_metric(f"model.generate.{model_name}", duration_ms, bool(result.text))
        return result

    def embed_text(self, text: str, model_name: str = "embedding_model") -> list[float] | None:
        started = time.perf_counter()
        model = self.load_model(model_name)
        try:
            embedding = model.embed_text(text) if hasattr(model, "embed_text") else None
        except Exception:
            embedding = None
        duration_ms = (time.perf_counter() - started) * 1000
        self._last_embedding_ms = duration_ms
        self._record_metric(f"model.embed.{model_name}", duration_ms, embedding is not None)
        return embedding

    def unload_unused_models(self) -> None:
        now = time.time()
        stale = [
            alias
            for alias, handle in self._loaded.items()
            if not handle.external and (now - handle.last_used) > self.idle_ttl_sec
        ]
        for alias in stale:
            self._close_alias(alias)

    def close(self) -> None:
        closed_external: set[int] = set()
        for alias in list(self._loaded.keys()):
            handle = self._loaded.get(alias)
            if handle is None:
                continue
            if handle.external:
                obj_id = id(handle.model)
                if obj_id in closed_external:
                    self._loaded.pop(alias, None)
                    continue
                closed_external.add(obj_id)
            self._close_alias(alias)

    def stats(self) -> dict[str, object]:
        return {
            "loaded_models": sorted(self._loaded.keys()),
            "loaded_count": len(self._loaded),
            "last_generation_ms": round(self._last_generation_ms, 2),
            "last_embedding_ms": round(self._last_embedding_ms, 2),
        }

    def _trim_cache(self) -> None:
        non_external = [item for item in self._loaded.items() if not item[1].external]
        if len(non_external) <= self.max_cached_models:
            return
        non_external.sort(key=lambda item: item[1].last_used)
        overflow = len(non_external) - self.max_cached_models
        for alias, _handle in non_external[:overflow]:
            self._close_alias(alias)

    def _close_alias(self, alias: str) -> None:
        handle = self._loaded.pop(alias, None)
        if handle is None:
            return
        if hasattr(handle.model, "close"):
            try:
                handle.model.close()
            except Exception:
                return

    @staticmethod
    def _build_local_model(spec: ModelSpec) -> LocalModel:
        return LocalModel(
            base_url=spec.base_url,
            model=spec.model_name,
            timeout_sec=spec.timeout_sec,
            manage_server=spec.manage_server,
            llama_dir=spec.llama_dir,
            model_path=spec.model_path,
            startup_timeout_sec=spec.startup_timeout_sec,
            max_tokens=spec.max_tokens,
        )

    def _record_metric(self, label: str, duration_ms: float, ok: bool) -> None:
        if self.performance_analyzer is None:
            return
        self.performance_analyzer.record(label, duration_ms, ok)


class RoutedModelClient:
    def __init__(
        self,
        manager: ModelManager,
        selector,
        *,
        default_task_type: str,
        role: str = "",
        fixed_alias: str | None = None,
    ) -> None:
        self.manager = manager
        self.selector = selector
        self.default_task_type = default_task_type
        self.role = role
        self.fixed_alias = fixed_alias

    def generate(self, prompt: str, context: dict[str, Any] | None = None) -> ModelResponse:
        alias = self.fixed_alias or self.selector.select_model(
            self.default_task_type,
            role=self.role,
            prompt=prompt,
            context=context,
        )
        return self.manager.generate(alias, prompt)

    def embed_text(self, text: str) -> list[float] | None:
        alias = self.fixed_alias or self.selector.select_model(
            "embedding",
            role=self.role,
            prompt=text,
            context={},
        )
        return self.manager.embed_text(text, alias)
