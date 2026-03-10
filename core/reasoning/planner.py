from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class PlanStep:
    step_id: str
    title: str
    capability: str
    status: str = "pending"


@dataclass(slots=True)
class GoalPlan:
    goal: str
    steps: list[PlanStep] = field(default_factory=list)


class Planner:
    def __init__(self, *, max_steps: int = 6) -> None:
        self.max_steps = max(3, max_steps)

    def build_plan(self, goal: str) -> GoalPlan:
        text = goal.strip()
        lowered = text.lower()
        steps: list[PlanStep] = [
            PlanStep("step-1", "Understand the goal", "conversation"),
        ]

        if any(keyword in lowered for keyword in ("research", "compare", "find", "summarize", "best")):
            steps.extend(
                [
                    PlanStep("step-2", "Search the web for relevant sources", "research"),
                    PlanStep("step-3", "Parse source content and extract evidence", "research"),
                    PlanStep("step-4", "Store findings in the knowledge base", "memory"),
                    PlanStep("step-5", "Synthesize a final summary", "conversation"),
                ]
            )
        elif any(keyword in lowered for keyword in ("open", "launch", "run", "schedule")):
            steps.extend(
                [
                    PlanStep("step-2", "Determine required automation action", "planning"),
                    PlanStep("step-3", "Execute the automation step", "automation"),
                    PlanStep("step-4", "Confirm outcome and report back", "conversation"),
                ]
            )
        else:
            steps.extend(
                [
                    PlanStep("step-2", "Recall relevant context from memory", "memory"),
                    PlanStep("step-3", "Reason about the best answer", "planning"),
                    PlanStep("step-4", "Respond with context-aware guidance", "conversation"),
                ]
            )

        return GoalPlan(goal=text, steps=steps[: self.max_steps])
