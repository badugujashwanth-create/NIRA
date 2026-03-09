from __future__ import annotations

from nira.intelligence.planner import Planner
from nira.task_graph.graph import TaskGraph


class TaskGraphPlanner:
    def __init__(self, planner: Planner) -> None:
        self.planner = planner

    def build_graph(self, goal: str, intent, context: dict[str, object], memory_hits: dict[str, object], guidance: str = "") -> TaskGraph:
        tasks = self.planner.build_plan(goal, intent, context, memory_hits, guidance)
        return TaskGraph.from_planned_tasks(tasks)
