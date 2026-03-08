from __future__ import annotations

from nira_agent.memory.long_term import MemoryRecord
from nira_agent.memory.short_term import Turn
from nira_agent.ui.app_state import AgentState


class ContextBuilder:
    def build(
        self,
        state: AgentState,
        short_term: list[Turn],
        long_term: list[MemoryRecord],
        compressed_summary: str,
        proactive_hint: str,
    ) -> str:
        memory_lines = [f"[{m.kind}] {m.content}" for m in long_term[-5:]]
        short_lines = [f"{t.role}: {t.content}" for t in short_term[-6:]]
        return "\n".join(
            [
                f"Mode: {state.mode}",
                f"Tone: {state.tone}",
                f"DND: {state.dnd}",
                f"Compressed Summary: {compressed_summary}",
                f"Proactive State Hint: {proactive_hint}",
                "Long-Term Memory:",
                *memory_lines,
                "Recent Turns:",
                *short_lines,
            ]
        )

