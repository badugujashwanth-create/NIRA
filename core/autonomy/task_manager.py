from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.reasoning import GoalPlan


@dataclass(slots=True)
class TaskRecord:
    step_id: str
    title: str
    capability: str
    status: str = "pending"
    result: str = ""


class TaskManager:
    def __init__(self) -> None:
        self._background_tasks: list[asyncio.Task] = []

    def create_records(self, plan: GoalPlan) -> list[TaskRecord]:
        return [TaskRecord(step.step_id, step.title, step.capability) for step in plan.steps]

    def mark_running(self, record: TaskRecord) -> None:
        record.status = "running"

    def mark_completed(self, record: TaskRecord, result: str) -> None:
        record.status = "completed"
        record.result = result

    def mark_failed(self, record: TaskRecord, result: str) -> None:
        record.status = "failed"
        record.result = result

    def submit_background(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        return task

    async def drain_background(self) -> None:
        if not self._background_tasks:
            return
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
