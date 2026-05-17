from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from nira_core.telemetry import Telemetry


WorkflowHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    """One named async workflow step."""

    name: str
    handler: str
    params: dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """Small workflow coordinator for multi-step local tasks."""

    def __init__(self, telemetry: Telemetry) -> None:
        self._handlers: dict[str, WorkflowHandler] = {}
        self._telemetry = telemetry

    def register(self, name: str, handler: WorkflowHandler) -> None:
        self._handlers[name] = handler

    async def run(self, steps: list[WorkflowStep], initial_state: dict[str, Any] | None = None) -> dict[str, Any]:
        state = dict(initial_state or {})
        for step in steps:
            self._telemetry.emit("workflow.step.start", {"name": step.name, "handler": step.handler})
            handler = self._handlers[step.handler]
            state.update(step.params)
            state = await handler(state)
            self._telemetry.emit("workflow.step.finish", {"name": step.name})
        return state
