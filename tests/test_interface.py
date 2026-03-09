from __future__ import annotations

import unittest
from types import SimpleNamespace

from nira.interface.interface_manager import InterfaceManager
from nira.interface.task_visualizer import TaskVisualizer


class FakeRuntime:
    def __init__(self) -> None:
        self.config = SimpleNamespace(
            enable_notifications=False,
            enable_voice=False,
            enable_overlay=False,
        )
        self.system_metrics = SimpleNamespace(snapshot=lambda: {"cpu": 0})
        self._listeners = []
        self.shutdown_called = False

    def add_status_listener(self, listener) -> None:
        self._listeners.append(listener)

    def handle(self, text: str):
        tasks = [
            {"task_id": "1", "description": "Analyze project", "tool": "analyze_project", "status": "completed"},
            {"task_id": "2", "description": "Generate code", "tool": "generate_code", "status": "running"},
        ]
        for listener in self._listeners:
            listener({"event": "planning_started", "message": "Planning integration...", "tasks": tasks, "payload": {}})
            listener({"event": "task_progress", "message": "Running Generate code.", "tasks": tasks, "payload": {}})
        state = SimpleNamespace(
            context={
                "active_project": "Android App",
                "language": "Kotlin",
                "last_error": "Gradle dependency mismatch",
                "cwd": "C:/workspace/android-app",
            },
            intent={"kind": "coding"},
        )
        return SimpleNamespace(text="Planning integration...", state=state, plan=tasks, task_results=[{"ok": True}], anomalies=[])

    def shutdown(self) -> None:
        self.shutdown_called = True


class InterfaceTests(unittest.TestCase):
    def test_task_visualizer_formats_goal_and_status(self) -> None:
        visualizer = TaskVisualizer()
        text = visualizer.render_text(
            [
                {"description": "Analyze project", "status": "completed"},
                {"description": "Generate code", "status": "running"},
            ],
            goal="Integrate Authentication",
        )
        self.assertIn("Goal: Integrate Authentication", text)
        self.assertIn("[done] Analyze project", text)
        self.assertIn("[running] Generate code", text)

    def test_interface_manager_handles_runtime_flow(self) -> None:
        manager = InterfaceManager(FakeRuntime(), prefer_gui=False)
        response = manager.handle_user_input("Add Firebase authentication")
        self.assertIsNotNone(response)
        self.assertEqual(manager.chat.history[0]["role"], "user")
        self.assertEqual(manager.chat.history[1]["role"], "assistant")
        self.assertIn("Goal: Add Firebase authentication", manager.task_visualizer.render_text())
        self.assertEqual(manager.notifications.history[-1].level, "success")


if __name__ == "__main__":
    unittest.main()
