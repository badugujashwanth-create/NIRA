from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from nira.task_graph.node import TaskNode


@dataclass
class TaskGraph:
    nodes: list[TaskNode] = field(default_factory=list)
    arguments: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_planned_tasks(cls, tasks: Iterable[object]) -> "TaskGraph":
        nodes: list[TaskNode] = []
        arguments: dict[str, dict[str, Any]] = {}
        for task in tasks:
            task_id = getattr(task, "task_id")
            nodes.append(
                TaskNode(
                    task_id=task_id,
                    description=getattr(task, "description"),
                    tool=getattr(task, "tool"),
                    dependencies=list(getattr(task, "dependencies", [])),
                )
            )
            arguments[task_id] = dict(getattr(task, "args", {}))
        return cls(nodes=nodes, arguments=arguments)

    def get_node(self, task_id: str) -> TaskNode | None:
        for node in self.nodes:
            if node.task_id == task_id:
                return node
        return None

    def ready_nodes(self) -> list[TaskNode]:
        ready: list[TaskNode] = []
        for node in self.nodes:
            if node.status not in {"pending", "ready"}:
                continue
            if all(
                self.get_node(dep) and self.get_node(dep).status in {"completed", "repaired"}
                for dep in node.dependencies
            ):
                node.status = "ready"
                ready.append(node)
        return ready

    def block_dependents(self, task_id: str) -> None:
        for node in self.nodes:
            if task_id in node.dependencies and node.status in {"pending", "ready"}:
                node.status = "blocked"
