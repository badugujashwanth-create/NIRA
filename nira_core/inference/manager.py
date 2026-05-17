from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping

from nira_core.config import ModelSpec, NiraConfig
from nira_core.events import Event, EventBus, EventType
from nira_core.inference.base import InferenceBackend, InferenceRequest, InferenceResult, result_from_text
from nira_core.inference.llamacpp import LlamaCppBackend
from nira_core.inference.ollama import OllamaBackend
from nira_core.state import SystemState
from nira_core.telemetry import Telemetry


class LocalInferenceManager:
    """Serialize local inference and swap heavy models before loading another."""

    def __init__(
        self,
        config: NiraConfig,
        telemetry: Telemetry,
        backends: Mapping[str, InferenceBackend] | None = None,
        state: SystemState | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config
        self._telemetry = telemetry
        self._state = state
        self._event_bus = event_bus
        self._inference_lock = asyncio.Lock()
        self._swap_lock = asyncio.Lock()
        self._current_heavy_alias: str | None = None
        self._provider_failures: dict[str, int] = {}
        self._provider_cooldown_until: dict[str, float] = {}
        self._backends: dict[str, InferenceBackend] = dict(backends or {})
        self._backends.setdefault("ollama", OllamaBackend(config.runtime))
        self._backends.setdefault("llama.cpp", LlamaCppBackend(config.runtime))
        self._backends.setdefault("llamacpp", self._backends["llama.cpp"])

    @property
    def current_heavy_alias(self) -> str | None:
        """Return the currently retained heavy model alias, if any."""

        return self._current_heavy_alias

    def models(self) -> list[dict[str, object]]:
        """Return configured model metadata without secrets."""

        return [
            {
                "alias": spec.alias,
                "name": spec.name,
                "provider": spec.provider,
                "role": spec.role,
                "heavy": spec.heavy,
                "context_window": spec.context_window,
                "quantization": spec.quantization,
            }
            for spec in self._config.models.values()
        ]

    async def generate(self, request: InferenceRequest) -> InferenceResult:
        """Generate text while respecting CPU and RAM constraints."""

        alias = request.model_alias or self._config.routing.get(request.task_type, "fast")
        spec = self._config.model_for_alias(alias)
        await self._ensure_model_slot(spec)
        async with self._inference_lock:
            return await self._generate_locked(spec, request)

    async def _generate_locked(self, spec: ModelSpec, request: InferenceRequest) -> InferenceResult:
        started = time.perf_counter()
        try:
            await self._emit_start(spec, request)
            if self._provider_in_cooldown(spec.provider):
                raise RuntimeError(f"provider_in_cooldown:{spec.provider}")
            result = await self._backend_for(spec).generate(spec, request)
            self._record_provider_success(spec.provider)
            await self._record_result(result)
            return result
        except Exception as exc:
            self._record_provider_failure(spec.provider)
            self._telemetry.increment("inference_failures_total")
            self._telemetry.emit("inference.error", {"model_alias": spec.alias, "error": str(exc)})
            fallback_alias = self._config.routing.get("classification", "fast")
            if spec.alias != fallback_alias and fallback_alias in self._config.models:
                fallback = self._config.model_for_alias(fallback_alias)
                self._telemetry.increment("inference_fallback_total")
                self._telemetry.emit("inference.fallback", {"from": spec.alias, "to": fallback.alias})
                try:
                    await self._emit_start(fallback, request)
                    if self._provider_in_cooldown(fallback.provider):
                        raise RuntimeError(f"provider_in_cooldown:{fallback.provider}")
                    result = await self._backend_for(fallback).generate(fallback, request)
                    self._record_provider_success(fallback.provider)
                    await self._record_result(result)
                    return result
                except Exception as fallback_exc:
                    self._record_provider_failure(fallback.provider)
                    self._telemetry.emit("inference.fallback_error", {"model_alias": fallback.alias, "error": str(fallback_exc)})
            text = (
                "Local inference is currently unavailable. NIRA kept the workflow alive, "
                "recorded the failure, and will recover when the model backend responds again."
            )
            result = result_from_text(text, spec, request.prompt, started, {"degraded": True, "error": str(exc)})
            await self._record_result(result)
            return result

    async def _emit_start(self, spec: ModelSpec, request: InferenceRequest) -> None:
        if self._state is not None:
            self._state.set_active_model(spec.alias)
        self._telemetry.emit("inference.start", {"model_alias": spec.alias, "task_type": request.task_type})
        if self._event_bus is not None:
            await self._event_bus.publish(
                Event.create(EventType.INFERENCE_STARTED, {"model_alias": spec.alias, "task_type": request.task_type})
            )

    async def _record_result(self, result: InferenceResult) -> None:
        self._telemetry.record_inference(result)
        self._telemetry.emit(
            "inference.finish",
            {
                "model_alias": result.model_alias,
                "duration_sec": result.duration_sec,
                "prompt_tokens": result.token_accounting.prompt_tokens,
                "completion_tokens": result.token_accounting.completion_tokens,
            },
        )
        if self._state is not None:
            self._state.record_latency("inference", result.duration_sec * 1000.0)
        if self._event_bus is not None:
            await self._event_bus.publish(
                Event.create(
                    EventType.INFERENCE_COMPLETED,
                    {
                        "model_alias": result.model_alias,
                        "duration_sec": result.duration_sec,
                        "prompt_tokens": result.token_accounting.prompt_tokens,
                        "completion_tokens": result.token_accounting.completion_tokens,
                    },
                )
            )

    async def _ensure_model_slot(self, spec: ModelSpec) -> None:
        if not spec.heavy:
            return
        async with self._swap_lock:
            if self._current_heavy_alias == spec.alias:
                return
            if self._current_heavy_alias:
                previous = self._config.model_for_alias(self._current_heavy_alias)
                await self._backend_for(previous).unload(previous)
                if self._state is not None:
                    self._state.remove_resident_model(previous.alias)
                self._telemetry.increment("model_swaps_total")
                self._telemetry.emit(
                    "model.swap",
                    {"from": previous.alias, "to": spec.alias, "reason": "single-heavy-model-policy"},
                )
                if self._event_bus is not None:
                    self._event_bus.publish_nowait(
                        Event.create(
                            EventType.MODEL_SWAPPED,
                            {"from": previous.alias, "to": spec.alias, "reason": "single-heavy-model-policy"},
                        )
                    )
            else:
                self._telemetry.emit("model.load", {"alias": spec.alias, "reason": "first-heavy-model"})
            self._current_heavy_alias = spec.alias
            if self._state is not None:
                self._state.set_active_model(spec.alias)

    async def unload_current_heavy(self, reason: str = "manual") -> None:
        """Unload the resident heavy model when resource pressure requires it."""

        async with self._swap_lock:
            if not self._current_heavy_alias:
                return
            previous = self._config.model_for_alias(self._current_heavy_alias)
            await self._backend_for(previous).unload(previous)
            self._telemetry.increment("model_unloads_total")
            self._telemetry.emit("model.unload", {"alias": previous.alias, "reason": reason})
            if self._state is not None:
                self._state.remove_resident_model(previous.alias)
            self._current_heavy_alias = None

    def _backend_for(self, spec: ModelSpec) -> InferenceBackend:
        try:
            return self._backends[spec.provider]
        except KeyError as exc:
            raise KeyError(f"No inference backend configured for provider: {spec.provider}") from exc

    def _provider_in_cooldown(self, provider: str) -> bool:
        return time.monotonic() < self._provider_cooldown_until.get(provider, 0.0)

    def _record_provider_success(self, provider: str) -> None:
        self._provider_failures[provider] = 0
        self._provider_cooldown_until.pop(provider, None)

    def _record_provider_failure(self, provider: str) -> None:
        failures = self._provider_failures.get(provider, 0) + 1
        self._provider_failures[provider] = failures
        if failures >= 3:
            self._provider_cooldown_until[provider] = time.monotonic() + min(60.0, 5.0 * failures)
            self._telemetry.increment("inference_circuit_breaker_total")
            self._telemetry.emit("inference.circuit_breaker", {"provider": provider, "failures": failures})
