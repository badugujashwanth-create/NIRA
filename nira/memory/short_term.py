from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

from nira_agent.performance import PerformanceGuard


@dataclass
class Turn:
    role: str
    content: str


class ShortTermMemory:
    def __init__(self, max_turns: int, compress_every_n_turns: int, token_threshold: int = 900) -> None:
        self.max_turns = max_turns
        self.compress_every_n_turns = max(2, compress_every_n_turns)
        self.token_threshold = max(120, token_threshold)
        self._turns: deque[Turn] = deque(maxlen=max_turns)
        self._lock = threading.Lock()
        self._since_last_compress = 0
        self._estimated_tokens = 0

    def add_turn(self, role: str, content: str) -> None:
        with self._lock:
            if len(self._turns) == self._turns.maxlen and self._turns:
                # Keep approximate token tracking stable when deque evicts old items.
                dropped = self._turns[0]
                self._estimated_tokens = max(
                    0,
                    self._estimated_tokens - PerformanceGuard.estimate_tokens(dropped.content),
                )
            self._turns.append(Turn(role=role, content=content))
            self._since_last_compress += 1
            self._estimated_tokens += PerformanceGuard.estimate_tokens(content)

    def should_compress(self) -> bool:
        with self._lock:
            return (
                self._since_last_compress >= self.compress_every_n_turns
                or self._estimated_tokens >= self.token_threshold
            )

    def mark_compressed(self) -> None:
        with self._lock:
            self._since_last_compress = 0

    def replace_with_summary(self, summary: str, keep_recent_turns: int = 2) -> None:
        with self._lock:
            recent = list(self._turns)[-max(0, keep_recent_turns) :]
            self._turns.clear()
            if summary.strip():
                self._turns.append(Turn(role="system_summary", content=summary.strip()))
            for turn in recent:
                self._turns.append(turn)
            self._estimated_tokens = sum(PerformanceGuard.estimate_tokens(t.content) for t in self._turns)
            self._since_last_compress = 0

    def estimated_tokens(self) -> int:
        with self._lock:
            return self._estimated_tokens

    def snapshot(self) -> list[Turn]:
        with self._lock:
            return list(self._turns)
