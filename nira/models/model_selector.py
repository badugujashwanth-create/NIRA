from __future__ import annotations

from typing import Any

from nira.models.model_registry import ModelRegistry


class ModelSelector:
    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def select_model(
        self,
        task_type: str,
        *,
        role: str = "",
        prompt: str = "",
        context: dict[str, Any] | None = None,
    ) -> str:
        normalized = task_type.strip().lower() or role.strip().lower() or "quick"
        context = context or {}
        if normalized in {"embedding", "retrieval", "memory"}:
            return "embedding_model"
        if normalized in {"planning", "planner", "reasoning"}:
            return "planner_model"
        if normalized in {"coding", "implementation", "code"}:
            return "coding_model"
        if normalized in {"research", "research_topic", "analysis"}:
            return "research_model"
        if normalized in {"document", "documentation"}:
            return "planner_model"
        if normalized in {"safety", "risk"}:
            return "planner_model"
        if normalized in {"emotion", "chat", "quick"}:
            if len(prompt) <= 220 and not context.get("retrieved_knowledge"):
                return "fast_model"
            return "planner_model"
        return "fast_model" if len(prompt) <= 220 else "planner_model"
