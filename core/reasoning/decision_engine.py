from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from core.reasoning.planner import PlanStep


@dataclass(slots=True)
class Decision:
    agent_name: str
    rationale: str


class DecisionEngine:
    @lru_cache(maxsize=128)
    def choose_agent(self, capability: str) -> Decision:
        mapping = {
            "conversation": Decision("conversation", "Direct user communication and synthesis."),
            "planning": Decision("planning", "Task decomposition and execution control."),
            "research": Decision("research", "Internet search, parsing, and summarization."),
            "automation": Decision("automation", "System actions and external operations."),
            "memory": Decision("memory", "Knowledge retrieval and persistence."),
        }
        return mapping.get(capability, Decision("conversation", "Fallback conversation handling."))

    def choose_for_step(self, step: PlanStep) -> Decision:
        return self.choose_agent(step.capability)
