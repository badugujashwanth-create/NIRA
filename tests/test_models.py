from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nira.agents.coding_agent import CodingAgent
from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime
from nira.models import ModelContextBuilder, ModelManager, ModelRegistry, ModelResponse, ModelSelector


class StubBackend:
    def __init__(self, alias: str) -> None:
        self.alias = alias
        self.closed = False

    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text=f"{self.alias}::{prompt[:24]}", provider=self.alias)

    def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), float(len(self.alias))]

    def close(self) -> None:
        self.closed = True


class FakeRuntimeModel:
    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text="runtime-fake-response", provider="fake-runtime")

    def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]

    def close(self) -> None:
        return None


class MultiModelTests(unittest.TestCase):
    def test_model_registry_builds_default_aliases(self) -> None:
        config = NiraConfig(base_dir=Path(tempfile.mkdtemp()))
        registry = ModelRegistry.from_config(config)
        mapping = registry.to_mapping()
        self.assertIn("planner_model", mapping)
        self.assertIn("coding_model", mapping)
        self.assertIn("fast_model", mapping)
        self.assertIn("embedding_model", mapping)

    def test_model_selector_chooses_expected_aliases(self) -> None:
        config = NiraConfig(base_dir=Path(tempfile.mkdtemp()))
        selector = ModelSelector(ModelRegistry.from_config(config))
        self.assertEqual(selector.select_model("coding", prompt="write tests"), "coding_model")
        self.assertEqual(selector.select_model("planning", prompt="plan auth"), "planner_model")
        self.assertEqual(selector.select_model("research", prompt="research android auth"), "research_model")
        self.assertEqual(selector.select_model("quick", prompt="hi"), "fast_model")

    def test_model_manager_caches_and_unloads_idle_models(self) -> None:
        config = NiraConfig(base_dir=Path(tempfile.mkdtemp()))
        registry = ModelRegistry.from_config(config)
        manager = ModelManager(
            registry,
            max_cached_models=1,
            idle_ttl_sec=30,
            model_factory=lambda spec: StubBackend(spec.alias),
        )
        planning = manager.load_model("planner_model")
        self.assertEqual(planning.alias, "planner_model")
        coding = manager.load_model("coding_model")
        self.assertEqual(coding.alias, "coding_model")
        self.assertEqual(manager.stats()["loaded_count"], 1)
        self.assertTrue(planning.closed)
        manager._loaded["coding_model"].last_used = 0.0
        manager.unload_unused_models()
        self.assertEqual(manager.stats()["loaded_count"], 0)

    def test_role_agent_uses_selector_and_manager(self) -> None:
        config = NiraConfig(base_dir=Path(tempfile.mkdtemp()))
        registry = ModelRegistry.from_config(config)
        selector = ModelSelector(registry)
        manager = ModelManager(registry, model_factory=lambda spec: StubBackend(spec.alias))
        agent = CodingAgent(manager, selector, ModelContextBuilder(max_chars=1200))
        response = agent.respond("Implement authentication", {"active_project": "android-app", "language": "Kotlin"})
        self.assertEqual(response.metadata["model_alias"], "coding_model")
        self.assertIn("coding_model::", response.text)

    def test_agent_runtime_records_model_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = NiraConfig(base_dir=Path(tmp))
            runtime = AgentRuntime(config=config, model=FakeRuntimeModel())
            response = runtime.handle("Research Android authentication methods")
            self.assertTrue(response.state.context["model_stats"]["loaded_count"] >= 1)
            breakdown = runtime.performance_analyzer.breakdown("model.")
            self.assertTrue(breakdown)
            runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
