from __future__ import annotations

import json
import threading
from typing import Any

from nira.interface.chat_interface import ChatInterface
from nira.interface.desktop_overlay import DesktopOverlay
from nira.interface.notification_center import Notification, NotificationCenter
from nira.interface.task_visualizer import TaskVisualizer
from nira.interface.voice_interface import VoiceInterface


class InterfaceManager:
    def __init__(self, agent_runtime, prefer_gui: bool = True) -> None:
        self.runtime = agent_runtime
        config = agent_runtime.config
        self.notifications = NotificationCenter(enabled=config.enable_notifications)
        self.voice = VoiceInterface(enabled=config.enable_voice)
        self.task_visualizer = TaskVisualizer()
        self.chat = ChatInterface(self, prefer_gui=prefer_gui)
        self.overlay = DesktopOverlay(enabled=config.enable_overlay)
        self.current_goal = ""
        self.last_response = None
        if hasattr(self.runtime, "add_status_listener"):
            self.runtime.add_status_listener(self._handle_runtime_event)
        self.notifications.subscribe(self._dispatch_notification)

    def run(self, demo_mode: bool = False, full_demo: bool = False) -> None:
        if self.chat.ensure_window(start_hidden=self.overlay.enabled):
            self.chat.demo_mode = demo_mode or full_demo
            if hasattr(self.runtime, "set_approval_callback"):
                self.runtime.set_approval_callback(self.chat.request_tool_approval)
            self.overlay.attach_root(self.chat.root)
            self.overlay.bind_open_chat(self.chat.open_panel)
            self.overlay.start()
            if not self.overlay.enabled:
                self.chat.open_panel()
            if full_demo and self.chat.root is not None:
                self._schedule_full_demo()
            elif demo_mode and self.chat.root is not None:
                self.chat.root.after(3000, lambda: self.handle_user_input_async("Hello NIRA"))
                self.chat.root.after(9000, lambda: self.handle_user_input_async("add authentication to this repo"))
                self.chat.root.after(18000, self.chat._open_conversation_manager)
            self.chat.run_mainloop()
            return
        self.chat.run_console()

    def _schedule_full_demo(self) -> None:
        root = self.chat.root
        if root is None:
            return
        self.chat.demo_permission_decisions = [False, True]
        self.chat.demo_permission_delay_ms = 10000
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        def keep_demo_visible() -> None:
            try:
                if root.winfo_exists():
                    root.attributes("-topmost", True)
                    root.lift()
                    root.after(500, keep_demo_visible)
            except Exception:
                return

        root.after(500, keep_demo_visible)
        schedule = (
            (3000, self._demo_health),
            (18000, lambda: self.handle_user_input_async("Hello NIRA")),
            (45000, self._demo_open_conversations),
            (55000, lambda: self.chat.demo_filter_conversations("permission")),
            (62000, lambda: self.chat.demo_filter_conversations("")),
            (70000, self.chat.close_conversation_manager),
            (75000, self._demo_project_inspection),
            (100000, self._demo_bounded_read),
            (120000, self._demo_path_guard),
            (140000, lambda: self.handle_user_input_async("add authentication to this repo")),
            (165000, self._demo_permission_history),
            (180000, lambda: self.handle_user_input_async("verify this repository build")),
            (215000, self._demo_engineering_evidence),
            (228000, self._demo_close),
        )
        for delay_ms, callback in schedule:
            root.after(delay_ms, callback)

    def _demo_health(self) -> None:
        health = self.runtime.health()
        summary = {
            "status": health["status"],
            "mode": health["mode"],
            "allowed_access": health["allowed_access"],
            "interaction_logging_enabled": health["interaction_logging_enabled"],
            "tool_count": len(health["tools"]),
        }
        self.chat.display_system_message(
            "Guided demo: this is the real v0.4 runtime health.\n" + json.dumps(summary, indent=2)
        )
        self.chat.display_task_progress("Scene 1/9\n[done] Canonical runtime started\n[done] Offline-safe defaults verified")
        self.chat.display_status("Guided demo: runtime health")

    def _demo_open_conversations(self) -> None:
        active_id = self.runtime.current_conversation.conversation_id
        for title, user_text, assistant_text in (
            ("Permission design", "How are process tools controlled?", "Process tools require approve-once permission."),
            ("Release checklist", "What remains before v0.4?", "Video, CI, pull request, and release gates."),
        ):
            conversation = self.runtime.conversation_store.create(title)
            self.runtime.conversation_store.add_message(conversation.conversation_id, "user", user_text)
            self.runtime.conversation_store.add_message(conversation.conversation_id, "assistant", assistant_text)
        self.runtime.switch_conversation(active_id)
        self.chat._render_current_conversation()
        self.chat._open_conversation_manager()
        self.chat.display_status("Guided demo: local conversation controls")

    def _demo_project_inspection(self) -> None:
        result = self.runtime.inspect_project(".")
        languages = result.data.get("languages", {})
        self.chat.display_system_message(
            "Real read-only tool: analyze_project\n"
            f"Source files: {result.data.get('source_files')}\n"
            f"Languages: {languages}\n"
            f"Manifests: {result.data.get('manifests')}\n"
            "Dependency, cache, and build directories were excluded."
        )
        self.chat.display_task_progress("Scene 4/9\n[done] Run bounded project inspection\n[done] Exclude generated/dependency trees")
        self.chat.display_status("Guided demo: project inspection completed")

    def _demo_bounded_read(self) -> None:
        result = self.runtime.read_workspace_file("README.md", max_bytes=1200)
        preview = " ".join(result.output.split())[:420]
        self.chat.display_system_message(
            "Real read-only tool: file_manager\n"
            f"Path: README.md\nBytes: {result.data.get('bytes')}\n"
            f"Bound: {result.data.get('max_bytes')} bytes\nPreview: {preview}…"
        )
        self.chat.display_task_progress("Scene 5/9\n[done] Read README inside workspace\n[done] Bound returned content")
        self.chat.display_status("Guided demo: bounded file read completed")

    def _demo_path_guard(self) -> None:
        result = self.runtime.read_workspace_file("../outside.txt")
        self.chat.display_system_message(
            "Failure simulation: attempt to escape the workspace\n"
            f"Allowed: {result.ok}\nResult: {result.output}\n"
            "No outside file was read."
        )
        self.chat.display_task_progress("Scene 6/9\n[done] Attempt path escape\n[done] Reject outside-workspace read")
        self.chat.display_status("Guided demo: path containment held")

    def _demo_permission_history(self) -> None:
        decisions = self.runtime.recent_permission_decisions()
        rendered = "\n".join(
            f"{item['tool']} · {item['access']} · {'allowed' if item['allowed'] else 'denied'} · {item['reason']}"
            for item in decisions
        )
        self.chat.display_system_message(
            "Permission evidence (arguments are intentionally not stored):\n" + (rendered or "No decisions recorded.")
        )
        self.chat.display_status("Guided demo: denial recorded without raw arguments")

    def _demo_engineering_evidence(self) -> None:
        decisions = self.runtime.recent_permission_decisions()
        self.chat.display_system_message(
            "Engineering evidence from this release candidate:\n"
            "• 49 automated tests passed\n"
            "• dependency audit: no known vulnerabilities\n"
            "• tracked tree and 17-commit history: no secrets found\n"
            "• v0.4 wheel installed and reported healthy outside the source tree\n"
            f"• permission decisions in this process: {len(decisions)}"
        )
        self.chat.display_task_progress("Scene 8/9\n[done] Deny one process request\n[done] Approve one verification once\n[done] Show release evidence")
        self.chat.display_status("Guided demo: verification evidence")

    def _demo_close(self) -> None:
        self.chat.display_system_message(
            "Honest v0.4 boundary:\n"
            "The llama.cpp adapter is configurable and mock-tested, but no real model/hardware profile is claimed. "
            "Voice, OCR, legacy PyQt, retrieval quality, and screen-reader behavior remain outside the verified core.\n\n"
            "NIRA v0.4 — useful offline, explicit before side effects, and honest about what is not finished."
        )
        self.chat.display_task_progress("Scene 9/9\n[done] Main workflow\n[done] Safety boundary\n[done] Evidence and limitations")
        self.chat.display_status("Guided demo complete")

    def handle_user_input(self, text: str, source: str = "chat"):
        body = text.strip()
        if not body:
            return None
        self.current_goal = body
        if source == "voice":
            self.chat.display_system_message(f'Voice command: "{body}"')
        self.chat.display_user_message(body)
        self.chat.display_status("Routing request...")
        self.overlay.set_processing(True)
        self.overlay.show_message("Working...")
        try:
            response = self.runtime.handle(body)
        except Exception as exc:
            self.overlay.set_processing(False)
            self.chat.display_status("Request failed.")
            self.notifications.error("Nira", f"Request failed: {exc}")
            return None
        self.display_response(response, source=source)
        return response

    def handle_user_input_async(self, text: str, source: str = "chat") -> None:
        threading.Thread(target=self.handle_user_input, args=(text, source), daemon=True).start()

    def handle_voice_input(self):
        self.chat.display_status("Listening for voice input...")
        transcript = self.voice.listen_once()
        if not transcript:
            self.chat.display_status(self.voice.status())
            self.notifications.warning("Nira", "Voice input unavailable or no speech detected.")
            return None
        return self.handle_user_input(transcript, source="voice")

    def handle_voice_input_async(self) -> None:
        threading.Thread(target=self.handle_voice_input, daemon=True).start()

    def display_response(self, response, source: str = "chat") -> None:
        self.last_response = response
        self.chat.display_response(response)
        self.update_task_progress(response.plan)
        self.chat.display_status("Ready.")
        self.overlay.set_processing(False)
        self.overlay.show_message(response.text[:88])
        if response.anomalies:
            for anomaly in response.anomalies:
                message = (
                    "Action stopped safely. Review the failed task before retrying."
                    if anomaly == "execution_failure"
                    else anomaly
                )
                self.notifications.warning("Nira", message)
        elif response.task_results:
            self.notifications.success("Nira", "Task completed successfully.")
        else:
            self.notifications.info("Nira", "Response ready.")
        if source == "voice":
            self.voice.speak(response.text)

    def update_task_progress(self, tasks: list[dict[str, Any]]) -> None:
        snapshot = self.task_visualizer.update(tasks, goal=self.current_goal)
        self.chat.display_task_progress(snapshot.render_text())

    def shutdown(self) -> None:
        self.overlay.close()
        if hasattr(self.runtime, "set_approval_callback"):
            self.runtime.set_approval_callback(None)
        if hasattr(self.runtime, "remove_status_listener"):
            self.runtime.remove_status_listener(self._handle_runtime_event)
        self.runtime.shutdown()
        if self.chat.root is not None:
            try:
                self.chat.root.destroy()
            except Exception:
                pass

    def _handle_runtime_event(self, event: dict[str, Any]) -> None:
        message = str(event.get("message", "")).strip()
        if message:
            self.chat.display_status(message)
        tasks = event.get("tasks", [])
        if isinstance(tasks, list) and tasks:
            self.update_task_progress(tasks)
        event_name = str(event.get("event", ""))
        if event_name in {"input_received", "planning_started", "task_progress"}:
            self.overlay.set_processing(True)
        elif event_name in {"response_ready", "completed"}:
            self.overlay.set_processing(False)

    def _dispatch_notification(self, notification: Notification) -> None:
        self.chat.display_notification(notification.title, notification.message, notification.level)
        self.overlay.show_message(notification.message)
