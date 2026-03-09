from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STATUS_MARKERS = {
    "completed": "[done]",
    "repaired": "[done]",
    "running": "[running]",
    "failed": "[failed]",
    "blocked": "[blocked]",
    "ready": "[ready]",
    "pending": "[pending]",
}


@dataclass
class TaskProgressSnapshot:
    goal: str = ""
    tasks: list[dict[str, Any]] = field(default_factory=list)

    def render_lines(self) -> list[str]:
        if not self.tasks:
            return ["No active tasks."]
        lines: list[str] = []
        if self.goal:
            lines.append(f"Goal: {self.goal}")
            lines.append("")
        for task in self.tasks:
            status = str(task.get("status", "pending")).lower()
            marker = STATUS_MARKERS.get(status, "[pending]")
            description = str(task.get("description") or task.get("tool") or task.get("task_id") or "task")
            lines.append(f"{marker} {description}")
        return lines

    def render_text(self) -> str:
        return "\n".join(self.render_lines())


class TaskVisualizer:
    def __init__(self) -> None:
        self.snapshot = TaskProgressSnapshot()

    def update(self, tasks: list[dict[str, Any]], goal: str = "") -> TaskProgressSnapshot:
        self.snapshot = TaskProgressSnapshot(goal=goal, tasks=[dict(task) for task in tasks])
        return self.snapshot

    def render_text(self, tasks: list[dict[str, Any]] | None = None, goal: str = "") -> str:
        if tasks is not None:
            self.update(tasks, goal)
        return self.snapshot.render_text()
