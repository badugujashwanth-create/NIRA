from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Turn:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class ShortTermMemory:
    def __init__(self, max_turns: int = 18) -> None:
        self.max_turns = max(2, max_turns)
        self._turns: deque[Turn] = deque(maxlen=self.max_turns)

    def add_turn(self, role: str, content: str) -> None:
        self._turns.append(Turn(role=role, content=content))

    def recent(self, limit: int | None = None) -> list[Turn]:
        items = list(self._turns)
        if limit is None:
            return items
        return items[-limit:]

    def snapshot(self) -> list[Turn]:
        return list(self._turns)
