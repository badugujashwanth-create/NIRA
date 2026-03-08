from __future__ import annotations

from nira_agent.memory.short_term import Turn


class ConversationCompressor:
    def compress(self, turns: list[Turn]) -> str:
        if not turns:
            return ""
        # Lightweight deterministic summarization with recency weighting.
        recent = turns[-10:]
        lines: list[str] = []
        total = len(recent)
        for idx, t in enumerate(recent, start=1):
            snippet = t.content.replace("\n", " ").strip()
            if len(snippet) > 160:
                snippet = snippet[:160] + "..."
            recency_weight = round(idx / max(1, total), 2)
            lines.append(f"[w={recency_weight}] {t.role}: {snippet}")
        return " | ".join(lines)
