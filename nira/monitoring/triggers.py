from __future__ import annotations

from dataclasses import dataclass

from nira_agent.monitoring.activity import ActivityEvent


@dataclass
class TriggerResult:
    fired: bool
    suggestion: str = ""


class TriggerEngine:
    def __init__(self, distraction_apps: list[str], idle_threshold_sec: int = 900) -> None:
        self.distraction_apps = {a.lower() for a in distraction_apps}
        self.idle_threshold_sec = max(60, idle_threshold_sec)
        self._last_window = ""
        self._repeat_count = 0

    def evaluate(self, event: ActivityEvent) -> TriggerResult:
        idle = self._idle_trigger(event)
        if idle.fired:
            return idle
        errors = self._error_repetition_trigger(event)
        if errors.fired:
            return errors
        distraction = self._distraction_trigger(event)
        if distraction.fired:
            return distraction
        return TriggerResult(False)

    def _idle_trigger(self, event: ActivityEvent) -> TriggerResult:
        if event.idle_seconds >= self.idle_threshold_sec:
            mins = int(event.idle_seconds // 60)
            return TriggerResult(True, f"You've been idle for {mins} min. Resume your last task?")
        return TriggerResult(False)

    def _error_repetition_trigger(self, event: ActivityEvent) -> TriggerResult:
        title = event.active_window_title.lower()
        if title and title == self._last_window and any(k in title for k in ("error", "failed", "exception")):
            self._repeat_count += 1
        else:
            self._repeat_count = 0
        self._last_window = title
        if self._repeat_count >= 2:
            self._repeat_count = 0
            return TriggerResult(True, "Repeated error windows detected. Want guided troubleshooting?")
        return TriggerResult(False)

    def _distraction_trigger(self, event: ActivityEvent) -> TriggerResult:
        proc = event.active_process_name.lower()
        if proc in self.distraction_apps and event.cpu_percent < 80:
            return TriggerResult(True, f"{event.active_process_name} is active. Switch to Focus mode?")
        return TriggerResult(False)

