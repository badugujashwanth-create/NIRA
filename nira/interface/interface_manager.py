from __future__ import annotations

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

    def run(self) -> None:
        if self.chat.ensure_window(start_hidden=self.overlay.enabled):
            self.overlay.attach_root(self.chat.root)
            self.overlay.bind_open_chat(self.chat.open_panel)
            self.overlay.start()
            if not self.overlay.enabled:
                self.chat.open_panel()
            self.chat.run_mainloop()
            return
        self.chat.run_console()

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
                self.notifications.warning("Nira", anomaly)
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
