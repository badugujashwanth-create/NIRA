from __future__ import annotations

from typing import Any


PROMPT_TEMPLATES = {
    "planner": (
        "You are NIRA's planning agent.\n"
        "Use the provided context to break the request into deterministic local steps.\n"
        "Context:\n{context}\n\n"
        "Request:\n{request}\n\n"
        "Return a concise operational response."
    ),
    "coding": (
        "You are NIRA's coding agent.\n"
        "Focus on repository-aware implementation details, safe edits, and local validation.\n"
        "Context:\n{context}\n\n"
        "Request:\n{request}\n\n"
        "Return concise engineering guidance."
    ),
    "research": (
        "You are NIRA's research agent.\n"
        "Prefer local evidence, stored knowledge, and offline reasoning before optional web use.\n"
        "Context:\n{context}\n\n"
        "Request:\n{request}\n\n"
        "Return a concise structured research response."
    ),
    "document": (
        "You are NIRA's document agent.\n"
        "Produce clear markdown-ready content grounded in the provided context.\n"
        "Context:\n{context}\n\n"
        "Request:\n{request}\n\n"
        "Return concise structured content."
    ),
    "safety": (
        "You are NIRA's safety agent.\n"
        "Assess risk, ambiguity, and whether the request should stay bounded and local.\n"
        "Context:\n{context}\n\n"
        "Request:\n{request}\n\n"
        "Return concise safety guidance."
    ),
    "emotion": (
        "You are NIRA's response-polishing agent.\n"
        "Keep the final response calm, direct, and minimally verbose.\n"
        "Context:\n{context}\n\n"
        "Draft:\n{request}\n\n"
        "Return the final user-facing response only."
    ),
}


class ModelContextBuilder:
    def __init__(self, max_chars: int = 4800) -> None:
        self.max_chars = max(1200, max_chars)

    def build(
        self,
        *,
        request: str,
        context: dict[str, Any] | None = None,
        role: str = "",
        active_task: str = "",
    ) -> str:
        context = context or {}
        sections = [
            self._section("Role", role or "general"),
            self._section("Active Project", context.get("active_project", "")),
            self._section("Language", context.get("language", "")),
            self._section("Active Task", active_task or context.get("active_task", "")),
            self._section("Project Context", self._project_context(context)),
            self._section("Retrieved Memory", self._memory_context(context)),
            self._section("Previous Conversation", self._conversation_context(context)),
            self._section("Request Focus", request.strip()),
        ]
        payload = "\n\n".join(section for section in sections if section)
        return self._truncate(payload)

    @staticmethod
    def render_prompt(role_name: str, request: str, context_text: str) -> str:
        template = PROMPT_TEMPLATES.get(role_name, PROMPT_TEMPLATES["planner"])
        return template.format(context=context_text or "(no additional context)", request=request.strip())

    @staticmethod
    def _section(title: str, value: Any) -> str:
        text = str(value).strip()
        if not text:
            return ""
        return f"{title}:\n{text}"

    def _project_context(self, context: dict[str, Any]) -> str:
        parts = [
            f"cwd={context.get('cwd', '')}",
            f"manifests={context.get('manifests', [])}",
            f"available_tools={context.get('available_tools', [])[:10]}",
            f"last_error={context.get('last_error', 'none')}",
        ]
        return "\n".join(part for part in parts if part.strip())

    def _memory_context(self, context: dict[str, Any]) -> str:
        retrieved = context.get("retrieved_knowledge", [])
        vector_hits = context.get("vector_hits", [])
        workflow_matches = context.get("workflow_matches", [])
        lines: list[str] = []
        if retrieved:
            lines.append(f"knowledge={retrieved[:3]}")
        if vector_hits:
            lines.append(f"semantic_hits={vector_hits[:3]}")
        if workflow_matches:
            lines.append(f"workflow_matches={workflow_matches[:2]}")
        return "\n".join(lines)

    def _conversation_context(self, context: dict[str, Any]) -> str:
        history = context.get("previous_conversation", [])
        if not isinstance(history, list) or not history:
            return ""
        rendered: list[str] = []
        for item in history[-6:]:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "turn")).strip() or "turn"
            text = str(item.get("text") or item.get("content") or "").strip()
            if not text:
                continue
            rendered.append(f"{role}: {text[:240]}")
        return "\n".join(rendered)

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_chars:
            return text
        return text[: self.max_chars - 18].rstrip() + "\n...[truncated]"
