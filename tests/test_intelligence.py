from __future__ import annotations

import unittest

from nira.intelligence.confidence import ConfidenceEngine
from nira.intelligence.intent_analyzer import IntentAnalyzer
from nira.intelligence.planner import Planner
from nira.models.llama_runtime import ModelResponse
from nira.research.topic_planner import TopicPlanner


class FakeModel:
    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text="planned", provider="fake")


class IntelligenceTests(unittest.TestCase):
    def test_intent_analyzer_detects_research_topic(self) -> None:
        analyzer = IntentAnalyzer()
        intent = analyzer.analyze("Research Android authentication methods")
        self.assertEqual(intent.kind, "research_topic")
        self.assertEqual(intent.agent_role, "research_agent")

    def test_topic_planner_returns_structured_plan(self) -> None:
        plan = TopicPlanner(model=None).plan("Research Android authentication methods")
        self.assertTrue(plan.topic)
        self.assertGreaterEqual(len(plan.subtopics), 4)

    def test_planner_emits_expected_coding_flow(self) -> None:
        planner = Planner(planner_agent=None)
        plan = planner.build_plan(
            "integrate authentication",
            IntentAnalyzer().analyze("integrate authentication"),
            {"manifests": ["requirements.txt"]},
            {},
        )
        self.assertEqual(
            [task.tool for task in plan],
            ["analyze_project", "add_dependency", "update_config", "generate_code", "run_build"],
        )

    def test_planner_emits_research_task_graph(self) -> None:
        planner = Planner(planner_agent=None)
        plan = planner.build_plan(
            "Research Android authentication methods",
            IntentAnalyzer().analyze("Research Android authentication methods"),
            {},
            {},
        )
        self.assertEqual(
            [task.tool for task in plan],
            ["plan_topic", "analyze_sources", "summarize_information", "generate_report", "store_knowledge"],
        )

    def test_confidence_engine_scores_success(self) -> None:
        engine = ConfidenceEngine()

        class Result:
            ok = True

        class Execution:
            results = [Result(), Result()]

        class State:
            plan = [{}, {}]
            memory_hits = {"short_term": [1], "vector_store": []}
            risk_level = "low"

        score = engine.score(State(), Execution())
        self.assertGreaterEqual(score, 0.9)


if __name__ == "__main__":
    unittest.main()
