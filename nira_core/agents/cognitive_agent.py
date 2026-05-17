from __future__ import annotations

from nira_core.agents.base import AgentResult
from nira_core.orchestration.engine import CognitiveOrchestrator


class CognitiveAgent:
    """Thin agent facade; intelligence lives in orchestration layers."""

    def __init__(self, orchestrator: CognitiveOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def run(self, task: str, task_type: str | None = None) -> AgentResult:
        """Run a task through routing, context distillation, and inference."""

        outcome = await self._orchestrator.run(task, task_type=task_type)
        return AgentResult(
            text=outcome.text,
            route=outcome.task_type,
            model_alias=outcome.model_alias,
            context_tokens=outcome.context_tokens,
            metadata=outcome.metadata,
        )
