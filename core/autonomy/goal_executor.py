from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config.logger import get_logger
from core.agents import AgentCoordinator, StepExecution
from core.autonomy.task_manager import TaskManager, TaskRecord
from core.monitoring import MetricsCollector
from core.reasoning import GoalPlan, Planner


@dataclass(slots=True)
class GoalExecutionResult:
    goal: str
    plan: GoalPlan
    tasks: list[TaskRecord]
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


class GoalExecutor:
    def __init__(
        self,
        *,
        planner: Planner,
        coordinator: AgentCoordinator,
        task_manager: TaskManager,
        metrics: MetricsCollector,
    ) -> None:
        self.planner = planner
        self.coordinator = coordinator
        self.task_manager = task_manager
        self.metrics = metrics
        self.logger = get_logger("nira.goal_executor")

    async def execute(self, goal: str) -> GoalExecutionResult:
        plan = self.planner.build_plan(goal)
        task_records = self.task_manager.create_records(plan)
        context: dict[str, Any] = {"goal": goal, "executions": [], "allow_plugins": False}
        self.metrics.increment("goals.executed")

        for step, record in zip(plan.steps, task_records):
            self.task_manager.mark_running(record)
            try:
                execution: StepExecution = await self.coordinator.execute_step(goal, step, context)
                context["executions"].append(execution)
                context.update(execution.metadata)
                self.task_manager.mark_completed(record, execution.output)
                self.logger.info(
                    "task.completed",
                    extra={"step_id": step.step_id, "agent": execution.agent_name},
                )
            except Exception as exc:
                self.metrics.increment("goals.failed")
                self.task_manager.mark_failed(record, str(exc))
                self.logger.exception("task.failed", extra={"step_id": step.step_id})
                break

        await self.task_manager.drain_background()
        summary = self._summarize(goal, context, task_records)
        return GoalExecutionResult(
            goal=goal,
            plan=plan,
            tasks=task_records,
            summary=summary,
            metadata={"metrics": self.metrics.summary()},
        )

    @staticmethod
    def _summarize(goal: str, context: dict[str, Any], tasks: list[TaskRecord]) -> str:
        completed = [task for task in tasks if task.status == "completed"]
        if completed and completed[-1].result:
            return completed[-1].result
        if context.get("executions"):
            last = context["executions"][-1]
            return last.output
        return f"NIRA processed the goal: {goal}"
