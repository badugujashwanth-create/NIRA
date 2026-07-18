from __future__ import annotations

import unittest
from types import SimpleNamespace

from nira.interface.interface_manager import InterfaceManager
from nira.interface.operations_center import OperationsCenterPresenter
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
    def test_operations_center_presents_all_runtime_domains(self) -> None:
        snapshot = {
            "mode": "deterministic-offline",
            "agents": [
                {
                    "name": "Safety",
                    "status": "ready",
                    "capability": "Permission boundaries",
                    "detail": "Risk classified as low",
                }
            ],
            "agent_trace": [{"agent": "Safety", "detail": "Risk classified as low"}],
            "memory": {
                "storage": "Local SQLite",
                "conversation_count": 2,
                "message_count": 8,
                "short_term_turns": 4,
                "research_items": 1,
                "current_conversation": {"title": "Portfolio", "message_count": 4, "pinned": True},
            },
            "workflows": {
                "template_count": 1,
                "templates": {"research_topic": {"steps": ["plan_topic", "store_knowledge"]}},
                "detection_threshold": 2,
                "last_plan": [{"task_id": "task-1", "description": "Inspect project", "status": "completed"}],
            },
            "models": {
                "runtime": {"enabled": False, "loaded_count": 0},
                "routes": {"planning": "planner_model"},
                "cache_limit": 3,
                "idle_ttl_seconds": 900,
            },
            "tools": {
                "count": 1,
                "registered": ["analyze_project"],
                "allowed_access": ["read", "state"],
                "recent_decisions": [],
            },
            "system": {
                "health": {
                    "status": "ready",
                    "mode": "deterministic-offline",
                    "database_ready": True,
                    "workspace": "C:/Users/private/workspace",
                    "state_directory": "C:/Users/private/.nira",
                },
                "resources": {"cpu_percent": 1.0, "memory_percent": 30.0, "rss_mb": 50.0},
                "performance": {"count": 2.0, "success_rate": 1.0, "avg_duration_ms": 4.2},
            },
        }

        sections = OperationsCenterPresenter(snapshot).sections()

        self.assertEqual(
            list(sections),
            ["Overview", "Agents", "Memory", "Workflows", "Models", "Tools & permissions", "System health"],
        )
        self.assertIn("NIRA OPERATIONS CENTER", sections["Overview"])
        self.assertIn("Safety  [READY]", sections["Agents"])
        self.assertIn("Portfolio", sections["Memory"])
        self.assertIn("research_topic", sections["Workflows"])
        self.assertIn("[COMPLETED] Inspect project", sections["Workflows"])
        self.assertIn("planner_model", sections["Models"])
        self.assertIn("analyze_project", sections["Tools & permissions"])
        self.assertIn("Status               ready", sections["System health"])
        self.assertNotIn("C:/Users/private", sections["System health"])

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
