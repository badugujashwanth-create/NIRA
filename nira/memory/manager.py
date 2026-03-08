from __future__ import annotations

from nira_agent.memory.compressor import ConversationCompressor
from nira_agent.memory.long_term import LongTermMemoryStore
from nira_agent.memory.short_term import ShortTermMemory


class MemoryManager:
    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: LongTermMemoryStore,
        compressor: ConversationCompressor,
    ) -> None:
        self.short_term = short_term
        self.long_term = long_term
        self.compressor = compressor
        self.latest_summary = ""

    def add_user_turn(self, content: str) -> None:
        self.short_term.add_turn("user", content)
        self._compress_if_needed()

    def add_assistant_turn(self, content: str) -> None:
        self.short_term.add_turn("assistant", content)
        self._compress_if_needed()

    def _compress_if_needed(self) -> None:
        if not self.short_term.should_compress():
            return
        snapshot = self.short_term.snapshot()
        summary = self.compressor.compress(snapshot)
        if summary:
            self.long_term.append("summary", summary)
            self.latest_summary = summary
            # Replace older raw turns with summary + most recent turns to control context growth.
            self.short_term.replace_with_summary(summary, keep_recent_turns=2)
        else:
            self.short_term.mark_compressed()

    def consistency_check(self) -> tuple[bool, str]:
        try:
            turns = self.short_term.snapshot()
            if not turns:
                return True, "Memory is empty but consistent."
            if self.short_term.estimated_tokens() <= 0:
                return False, "Estimated tokens are non-positive despite existing turns."
            if len(turns) > self.short_term.max_turns:
                return False, "Short-term memory exceeded configured max turns."
            return True, f"Memory consistent: turns={len(turns)}, est_tokens={self.short_term.estimated_tokens()}."
        except Exception as exc:
            return False, f"Memory consistency check error: {exc}"
