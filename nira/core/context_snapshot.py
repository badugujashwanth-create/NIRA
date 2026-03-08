from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from nira_agent.monitoring.activity import ActivityEvent


@dataclass(frozen=True)
class ContextSnapshot:
    active_window: str
    current_project_path: str
    recently_modified_files: list[str]
    recent_tool_failures: list[str]
    time_of_day: str
    user_idle_duration_sec: float
    frequently_used_tools: list[str]

    def summary(self) -> str:
        files = ", ".join(self.recently_modified_files) if self.recently_modified_files else "none"
        failures = ", ".join(self.recent_tool_failures) if self.recent_tool_failures else "none"
        tools = ", ".join(self.frequently_used_tools) if self.frequently_used_tools else "none"
        return (
            f"ContextSnapshot("
            f"active_window={self.active_window}; "
            f"project={self.current_project_path}; "
            f"recent_files={files}; "
            f"recent_tool_failures={failures}; "
            f"time_of_day={self.time_of_day}; "
            f"idle_sec={int(self.user_idle_duration_sec)}; "
            f"frequent_tools={tools})"
        )


class ContextSnapshotEngine:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def build(
        self,
        activity_event: ActivityEvent | None,
        recent_tool_failures: list[str],
        tool_usage: dict[str, int],
    ) -> ContextSnapshot:
        active_window = self._sanitize_window(activity_event.active_window_title if activity_event else "")
        idle_seconds = activity_event.idle_seconds if activity_event else 0.0
        return ContextSnapshot(
            active_window=active_window,
            current_project_path=str(self.project_root),
            recently_modified_files=self._recently_modified_files(),
            recent_tool_failures=self._recent_failures(recent_tool_failures),
            time_of_day=self._time_bucket(),
            user_idle_duration_sec=max(0.0, idle_seconds),
            frequently_used_tools=self._top_tools(tool_usage),
        )

    def _recently_modified_files(self) -> list[str]:
        rows: list[tuple[float, str]] = []
        scanned = 0
        for path in self.project_root.rglob("*"):
            if scanned > 2500:
                break
            scanned += 1
            if not path.is_file():
                continue
            rel = str(path.relative_to(self.project_root))
            if "__pycache__" in rel or rel.startswith(".git\\") or rel.startswith(".git/"):
                continue
            try:
                rows.append((path.stat().st_mtime, rel))
            except OSError:
                continue
        rows.sort(key=lambda item: item[0], reverse=True)
        return [name for _, name in rows[:6]]

    @staticmethod
    def _recent_failures(failures: Iterable[str]) -> list[str]:
        cleaned = [f.strip()[:96] for f in failures if f and f.strip()]
        return cleaned[-6:]

    @staticmethod
    def _top_tools(tool_usage: dict[str, int]) -> list[str]:
        ordered = sorted(tool_usage.items(), key=lambda item: item[1], reverse=True)
        return [name for name, _ in ordered[:5]]

    @staticmethod
    def _time_bucket() -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"

    @staticmethod
    def _sanitize_window(title: str) -> str:
        trimmed = " ".join((title or "").split())
        if not trimmed:
            return "N/A"
        if len(trimmed) > 80:
            return trimmed[:77] + "..."
        return trimmed
