from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.logger import get_logger
from core.agents.specialists import (
    AgentResult,
    AutomationAgent,
    ConversationAgent,
    MemoryAgent,
    PlanningAgent,
    ResearchWorkerAgent,
)
from core.monitoring import MetricsCollector
from core.reasoning import DecisionEngine, PlanStep


@dataclass(slots=True)
class StepExecution:
    step_id: str
    agent_name: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    def __init__(
        self,
        *,
        decision_engine: DecisionEngine,
        conversation_agent: ConversationAgent,
        planning_agent: PlanningAgent,
        research_agent: ResearchWorkerAgent,
        automation_agent: AutomationAgent,
        memory_agent: MemoryAgent,
        metrics: MetricsCollector,
    ) -> None:
        self.decision_engine = decision_engine
        self.metrics = metrics
        self.logger = get_logger("nira.coordinator")
        self.agents = {
            "conversation": conversation_agent,
            "planning": planning_agent,
            "research": research_agent,
            "automation": automation_agent,
            "memory": memory_agent,
        }

    async def execute_step(self, goal: str, step: PlanStep, context: dict[str, Any]) -> StepExecution:
        decision = self.decision_engine.choose_for_step(step)
        agent = self.agents[decision.agent_name]
        self.metrics.increment(f"agent.{decision.agent_name}.runs")
        self.logger.info(
            "agent.selected",
            extra={
                "step_id": step.step_id,
                "agent": decision.agent_name,
                "rationale": decision.rationale,
            },
        )
        result: AgentResult = await agent.handle(goal, context)
        return StepExecution(
            step_id=step.step_id,
            agent_name=decision.agent_name,
            output=result.output,
            metadata=result.metadata,
        )

    async def converse(self, message: str) -> StepExecution:
        result = await self.agents["conversation"].handle(message, {})
        return StepExecution(step_id="conversation", agent_name="conversation", output=result.output, metadata=result.metadata)
