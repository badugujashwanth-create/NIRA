from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskNode:
    task_id: str
    description: str
    tool: str
    status: str = "pending"
    dependencies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "tool": self.tool,
            "status": self.status,
            "dependencies": list(self.dependencies),
        }
