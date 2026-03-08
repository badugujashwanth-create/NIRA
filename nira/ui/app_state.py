from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AgentState:
    mode: str = "Focus"
    tone: str = "concise"
    last_user_input: str = ""
    last_response: str = ""
    dnd: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StateStore:
    def __init__(self) -> None:
        self._state = AgentState()
        self._lock = threading.Lock()

    def get(self) -> AgentState:
        with self._lock:
            return AgentState(**self._state.__dict__)

    def update(self, **kwargs: str | bool) -> AgentState:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._state.updated_at = datetime.now(timezone.utc).isoformat()
            return AgentState(**self._state.__dict__)

