from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from nira.monitoring.activity_tracker import ActivitySnapshot


@dataclass
class Suggestion:
    text: str
    speak: bool = False


class ProactiveLogic:
    ERROR_MARKERS = ("error", "failed", "exception", "not responding")

    def __init__(
        self,
        cooldown_sec: int,
        idle_threshold_sec: int,
        distraction_apps: list[str],
        distraction_min_sec: int,
        tts_enabled: bool = False,
    ) -> None:
        self.cooldown_sec = max(5, cooldown_sec)
        self.idle_threshold_sec = max(30, idle_threshold_sec)
        self.distraction_apps = {app.lower() for app in distraction_apps}
        self.distraction_min_sec = max(60, distraction_min_sec)
        self.tts_enabled = tts_enabled
        self._last_suggestion_ts = 0.0
        self._error_title_count: dict[str, int] = {}

    def evaluate(
        self,
        snapshot: ActivitySnapshot,
        dnd_enabled: bool,
        proactive_enabled: bool,
    ) -> Optional[Suggestion]:
        if not proactive_enabled or dnd_enabled:
            return None
        now = time.time()
        if now - self._last_suggestion_ts < self.cooldown_sec:
            return None

        suggestion = self._idle_rule(snapshot) or self._error_rule(snapshot) or self._distraction_rule(snapshot)
        if suggestion:
            self._last_suggestion_ts = now
        return suggestion

    def _idle_rule(self, snapshot: ActivitySnapshot) -> Optional[Suggestion]:
        if snapshot.idle_seconds > self.idle_threshold_sec:
            minutes = int(snapshot.idle_seconds // 60)
            return Suggestion(
                text=f"You have been idle for about {minutes} minute(s). Want to resume your last task?",
                speak=self.tts_enabled,
            )
        return None

    def _error_rule(self, snapshot: ActivitySnapshot) -> Optional[Suggestion]:
        title = snapshot.window_title.strip().lower()
        if not title:
            return None
        if any(marker in title for marker in self.ERROR_MARKERS):
            count = self._error_title_count.get(title, 0) + 1
            self._error_title_count[title] = count
            if count >= 3:
                self._error_title_count[title] = 0
                return Suggestion(
                    text="I noticed repeated error windows. Say 'help me debug this' for guided steps.",
                    speak=self.tts_enabled,
                )
        return None

    def _distraction_rule(self, snapshot: ActivitySnapshot) -> Optional[Suggestion]:
        proc = snapshot.process_name.lower()
        if proc in self.distraction_apps and snapshot.current_app_duration > self.distraction_min_sec:
            minutes = int(snapshot.current_app_duration // 60)
            return Suggestion(
                text=f"{snapshot.process_name} has been active for {minutes} minute(s). Want focus mode?",
                speak=self.tts_enabled,
            )
        return None

