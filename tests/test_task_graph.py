from __future__ import annotations

import unittest

from nira.intelligence.intent_analyzer import IntentAnalyzer
from nira.intelligence.planner import Planner
from nira.task_graph.executor import TaskGraphExecutor
from nira.task_graph.graph import TaskGraph
from nira.task_graph.planner import TaskGraphPlanner
from nira.tools import Tool, ToolRegistry, ToolResult


class FlakyTool(Tool):
    name = "do_work"
    description = "Flaky test tool"

    def run(self, args, state) -> ToolResult:
        if args.get("retry"):
            return ToolResult(True, "repaired")
        return ToolResult(False, "failed")


class DummyReflection:
    def suggest_repair(self, tool_name, args, output):
        repaired = dict(args)
        repaired["retry"] = True
        return repaired


class DummyState:
    current_task = None
    tool_result = {}
    context = {}


class TaskGraphTests(unittest.TestCase):
    def test_executor_repairs_failed_node(self) -> None:
        registry = ToolRegistry()
        registry.register(FlakyTool())

        class Task:
            task_id = "1"
            description = "Work"
            tool = "do_work"
            dependencies = []
            args = {}

        graph = TaskGraph.from_planned_tasks([Task()])
        execution = TaskGraphExecutor(registry, DummyReflection()).execute(graph, DummyState())
        self.assertTrue(execution.success)
        self.assertEqual(graph.nodes[0].status, "repaired")

    def test_executor_emits_progress_updates(self) -> None:
        registry = ToolRegistry()
        registry.register(FlakyTool())

        class Task:
            task_id = "1"
            description = "Work"
            tool = "do_work"
            dependencies = []
            args = {}

        events: list[dict[str, object]] = []
        graph = TaskGraph.from_planned_tasks([Task()])
        TaskGraphExecutor(registry, DummyReflection()).execute(graph, DummyState(), progress_callback=events.append)
        self.assertGreaterEqual(len(events), 4)
        self.assertTrue(any("Running Work." == event.get("message") for event in events))
        self.assertEqual(events[-1]["tasks"][0]["status"], "repaired")

    def test_task_graph_planner_builds_research_graph(self) -> None:
        planner = TaskGraphPlanner(Planner(planner_agent=None))
        graph = planner.build_graph(
            "Research Android authentication methods",
            IntentAnalyzer().analyze("Research Android authentication methods"),
            {},
            {},
        )
        self.assertEqual(len(graph.nodes), 5)
        self.assertEqual(graph.nodes[0].tool, "plan_topic")


if __name__ == "__main__":
    unittest.main()
