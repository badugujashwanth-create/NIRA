from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from nira_agent.monitoring.activity import ActivityEvent
from nira_agent.monitoring.triggers import TriggerEngine


@dataclass
class ProactiveState:
    last_suggestion: str = ""
    last_ts: float = 0.0
    latest_event: ActivityEvent | None = None


class ProactiveCoordinator:
    def __init__(self, trigger_engine: TriggerEngine, cooldown_sec: int = 300) -> None:
        self.trigger_engine = trigger_engine
        self.cooldown_sec = max(30, cooldown_sec)
        self._state = ProactiveState()
        self._lock = threading.Lock()

    def on_event(self, event: ActivityEvent, dnd: bool, proactive_enabled: bool) -> str | None:
        with self._lock:
            self._state.latest_event = event
            if dnd or not proactive_enabled:
                return None
            if (time.time() - self._state.last_ts) < self.cooldown_sec:
                return None

            trigger = self.trigger_engine.evaluate(event)
            if not trigger.fired:
                return None
            self._state.last_ts = time.time()
            self._state.last_suggestion = trigger.suggestion
            return trigger.suggestion

    def system_state_hint(self) -> str:
        with self._lock:
            event = self._state.latest_event
            if not event:
                return "No monitoring data yet."
            return (
                f"ActiveWindow={event.active_window_title or 'N/A'}; "
                f"Process={event.active_process_name or 'N/A'}; "
                f"IdleSec={int(event.idle_seconds)}; CPU={event.cpu_percent:.1f}%."
            )

    def latest_event(self) -> ActivityEvent | None:
        with self._lock:
            return self._state.latest_event
