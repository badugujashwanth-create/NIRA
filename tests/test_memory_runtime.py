from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime
from nira.memory.error_memory import ErrorMemory
from nira.memory.research_memory import ResearchEntry, ResearchMemory
from nira.memory.vector_store import VectorStore
from nira.memory.workflow_memory import WorkflowMemory
from nira.models.llama_runtime import ModelResponse


class FakeModel:
    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text="fake-response", provider="fake")

    def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]

    def close(self) -> None:
        return None


class MemoryRuntimeTests(unittest.TestCase):
    def test_vector_store_search_returns_hits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "runtime.db"
            store = VectorStore(db, FakeModel())
            store.add_text("conversation", "authentication design notes", {})
            hits = store.search("authentication")
            self.assertTrue(hits)

    def test_research_memory_records_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "runtime.db"
            memory = ResearchMemory(db)
            memory.store(
                ResearchEntry(
                    topic="Android Authentication",
                    summary="Firebase Auth is commonly used.",
                    concepts=["Firebase", "OAuth2", "JWT"],
                    references=["local_doc.md"],
                )
            )
            hits = memory.search("authentication")
            self.assertTrue(hits)

    def test_workflow_memory_records_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "runtime.db"
            memory = WorkflowMemory(db)
            memory.record_trace(["git_pull", "install_deps", "run_server"], True)
            hits = memory.search("install deps")
            self.assertTrue(hits)

    def test_error_memory_records_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "runtime.db"
            memory = ErrorMemory(db)

            class Result:
                ok = False
                output = "compile failure"

            class Execution:
                current_task = "run_build"
                results = [Result()]
                success = False

            memory.record_execution(Execution())
            hits = memory.search("compile")
            self.assertTrue(hits)

    def test_agent_runtime_research_request_stores_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = NiraConfig(base_dir=Path(tmp))
            runtime = AgentRuntime(config=config, model=FakeModel())
            response = runtime.handle("Research Android authentication methods")
            self.assertIn("research", response.text.lower())
            self.assertEqual(len(response.plan), 5)
            stored = runtime.research_memory.search("Android authentication")
            self.assertTrue(stored)
            runtime.shutdown()


if __name__ == "__main__":
    unittest.main()
