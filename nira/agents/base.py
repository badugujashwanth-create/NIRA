from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nira.models.prompt_templates import ModelContextBuilder


@dataclass
class AgentMessage:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseRoleAgent:
    system_prompt = "You are a local NIRA role agent."
    role_name = "planner"
    task_type = "quick"

    def __init__(self, model, model_selector=None, context_builder: ModelContextBuilder | None = None) -> None:
        self.model = model
        self.model_selector = model_selector
        self.context_builder = context_builder or ModelContextBuilder()

    def respond(self, user_prompt: str, context: dict[str, Any] | None = None) -> AgentMessage:
        context = context or {}
        active_task = str(context.get("active_task", "")).strip()
        context_text = self.context_builder.build(
            request=user_prompt,
            context=context,
            role=self.role_name,
            active_task=active_task,
        )
        prompt = self.context_builder.render_prompt(self.role_name, user_prompt, context_text)
        if not self.model:
            return AgentMessage(text="", metadata={"source": "noop"})
        alias = None
        if self.model_selector is not None and hasattr(self.model, "load_model"):
            alias = self.model_selector.select_model(
                self.task_type,
                role=self.role_name,
                prompt=user_prompt,
                context=context,
            )
        if alias is not None and hasattr(self.model, "load_model"):
            try:
                result = self.model.generate(alias, prompt)
            except Exception as exc:
                return AgentMessage(text="", metadata={"source": "error", "error": str(exc), "model_alias": alias})
        else:
            try:
                result = self.model.generate(prompt)
            except Exception as exc:
                return AgentMessage(text="", metadata={"source": "error", "error": str(exc), "model_alias": alias})
        return AgentMessage(
            text=result.text.strip(),
            metadata={
                "provider": getattr(result, "provider", "unknown"),
                "model_alias": alias,
                "role": self.role_name,
            },
        )
