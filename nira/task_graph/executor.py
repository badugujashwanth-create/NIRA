from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nira.task_graph.repair_loop import RepairLoop
from nira.tools import ToolRegistry, ToolResult

ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass
class ExecutionSummary:
    success: bool
    results: list[ToolResult] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    current_task: str | None = None


class TaskGraphExecutor:
    def __init__(self, registry: ToolRegistry, reflection_engine) -> None:
        self.registry = registry
        self.repair_loop = RepairLoop(reflection_engine)

    def execute(self, graph, state, progress_callback: ProgressCallback | None = None) -> ExecutionSummary:
        results: list[ToolResult] = []
        trace: list[str] = []
        state.context.setdefault("task_outputs", {})
        self._emit_progress(graph, state, progress_callback, message="Task graph ready.")
        while True:
            ready = graph.ready_nodes()
            if not ready:
                break
            node = ready[0]
            node.status = "running"
            state.current_task = node.task_id
            state.context["active_task"] = node.description or node.task_id
            self._emit_progress(
                graph,
                state,
                progress_callback,
                node=node,
                message=f"Running {node.description or node.tool}.",
            )
            args = graph.arguments.get(node.task_id, {})
            result = self.registry.execute(node.tool, args, state)
            self._record_task_output(state, node.task_id, node.tool, result)
            results.append(result)
            trace.append(node.tool)
            if result.ok:
                node.status = "completed"
                state.tool_result = result.to_dict()
                self._emit_progress(
                    graph,
                    state,
                    progress_callback,
                    node=node,
                    result=result,
                    message=f"Completed {node.description or node.tool}.",
                )
                continue

            node.status = "failed"
            self._emit_progress(
                graph,
                state,
                progress_callback,
                node=node,
                result=result,
                message=f"Failed {node.description or node.tool}.",
            )
            repair = self.repair_loop.decide(node, args, result)
            if repair.attempted:
                graph.arguments[node.task_id] = repair.args
                repaired = self.registry.execute(node.tool, repair.args, state)
                self._record_task_output(state, node.task_id, node.tool, repaired)
                results.append(repaired)
                trace.append(f"{node.tool}:repair")
                state.tool_result = repaired.to_dict()
                if repaired.ok:
                    node.status = "repaired"
                    self._emit_progress(
                        graph,
                        state,
                        progress_callback,
                        node=node,
                        result=repaired,
                        message=f"Repaired {node.description or node.tool}.",
                    )
                    continue
                self._emit_progress(
                    graph,
                    state,
                    progress_callback,
                    node=node,
                    result=repaired,
                    message=f"Repair failed for {node.description or node.tool}.",
                )
            graph.block_dependents(node.task_id)
            self._emit_progress(
                graph,
                state,
                progress_callback,
                node=node,
                result=result,
                message=f"Blocked dependent tasks after {node.description or node.tool}.",
            )
            return ExecutionSummary(False, results=results, trace=trace, current_task=node.task_id)

        state.context["active_task"] = state.current_task or ""
        self._emit_progress(graph, state, progress_callback, message="Task graph complete.")
        success = all(node.status in {"completed", "repaired"} for node in graph.nodes)
        return ExecutionSummary(success=success, results=results, trace=trace, current_task=state.current_task)

    @staticmethod
    def _record_task_output(state, task_id: str, tool_name: str, result: ToolResult) -> None:
        state.context["task_outputs"][task_id] = result.to_dict()
        state.context["task_outputs"][tool_name] = result.to_dict()

    @staticmethod
    def _emit_progress(
        graph,
        state,
        callback: ProgressCallback | None,
        *,
        node=None,
        result: ToolResult | None = None,
        message: str = "",
    ) -> None:
        tasks = [item.to_dict() for item in graph.nodes]
        state.context["progress"] = tasks
        if callback is None:
            return
        callback(
            {
                "event": "task_progress",
                "message": message,
                "tasks": tasks,
                "current_task": getattr(node, "task_id", state.current_task),
                "payload": {
                    "tool": getattr(node, "tool", None),
                    "result": result.to_dict() if result else None,
                },
            }
        )
