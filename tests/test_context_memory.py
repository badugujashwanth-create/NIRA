from __future__ import annotations

from pathlib import Path

import pytest

from nira_core.compression import ContextBudgeter, SemanticCompressor
from nira_core.compression.distillation import ContextDistillationPipeline
from nira_core.config import load_config
from nira_core.memory import MemoryManager, WorkingMemory
from nira_core.retrieval import BGEReranker, RetrievalPipeline
from nira_core.telemetry import Telemetry


def test_context_budgeter_caps_final_context() -> None:
    budgeter = ContextBudgeter(max_tokens=40)
    text = " ".join(f"token{i}" for i in range(300))
    result = budgeter.trim(text)
    assert result.tokens <= 40
    assert result.text


def test_working_memory_prunes_to_limit() -> None:
    memory = WorkingMemory(max_items=2, ttl_sec=60)
    memory.set("a", 1)
    memory.set("b", 2)
    memory.set("c", 3)
    assert len(memory) == 2
    assert memory.get("a") is None


@pytest.mark.asyncio
async def test_distillation_never_exceeds_final_budget(tmp_path: Path) -> None:
    config = load_config()
    telemetry = Telemetry(tmp_path / "telemetry")
    memory = MemoryManager(config, telemetry)
    memory.semantic.add(
        "doc-1",
        "Python tests should validate routing, context budgets, and memory pruning. "
        "Large unrelated context must not be stuffed into prompts. " * 20,
        {"kind": "test"},
    )
    retrieval = RetrievalPipeline(memory, BGEReranker(), telemetry)
    compressor = SemanticCompressor(None, telemetry, target_tokens=80)
    pipeline = ContextDistillationPipeline(retrieval, compressor, ContextBudgeter(120), telemetry)
    distilled = await pipeline.build_context("How should tests validate context budgets?", reserved_prompt_tokens=20)
    assert distilled.context_tokens <= 100
    assert "context" in distilled.context.lower()
