from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import asdict
from typing import Any, TextIO

from nira.config import ConfigLoader
from nira.core.agent_runtime import AgentRuntime, RuntimeResponse
from nira.interface.voice_interface import VoiceInterface
from nira.voice.wake_word import WakeWordDetector


class DesktopBridgeService:
    def __init__(
        self,
        runtime: AgentRuntime | None = None,
        voice: VoiceInterface | None = None,
        wake_word: WakeWordDetector | None = None,
        *,
        output: TextIO | None = None,
    ) -> None:
        self.output = output or sys.stdout
        self.runtime = runtime or self._build_runtime()
        self.voice = voice or VoiceInterface(enabled=True, tts_enabled=True)
        self.wake_word = wake_word or WakeWordDetector(enabled=True, keyword="nira")
        self._paused = False
        self._shutdown = False
        self._write_lock = threading.Lock()
        self._runtime_lock = threading.Lock()
        self._heartbeat_lock = threading.Lock()
        self._heartbeat_thread: threading.Thread | None = None
        self.runtime.add_status_listener(self._on_runtime_event)

    def start(self) -> None:
        with self._heartbeat_lock:
            if self._heartbeat_thread is None:
                self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, name="nira-desktop-heartbeat", daemon=True)
                self._heartbeat_thread.start()
        wake_status = self.wake_word.start(self._on_wake_word_detected)
        self.emit_event(
            "ready",
            {
                "service": "desktop_bridge",
                "state": self._state_payload(),
                "wake_word": asdict(wake_status),
            },
        )

    def serve_forever(self, input_stream: TextIO | None = None) -> None:
        stream = input_stream or sys.stdin
        self.start()
        for raw_line in stream:
            line = raw_line.strip()
            if not line:
                continue
            request_id: str | int | None = None
            try:
                payload = json.loads(line)
                request_id = payload.get("id")
            except json.JSONDecodeError as exc:
                self.emit_result(request_id, False, {"error": f"invalid_json: {exc}"})
                continue
            command = str(payload.get("command", "")).strip()
            result = self.handle_command(command, payload.get("payload", {}))
            self.emit_result(request_id, result.get("ok", False), result)
            if command == "shutdown":
                break

    def handle_command(self, command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        args = payload or {}
        command = command.strip().lower()
        if command == "ping":
            return {"ok": True, "pong": True, "state": self._state_payload()}
        if command == "get_state":
            return {"ok": True, "state": self._state_payload()}
        if command == "pause_assistant":
            self._paused = True
            self.emit_event("assistant_state", {"paused": True})
            return {"ok": True, "paused": True}
        if command == "resume_assistant":
            self._paused = False
            self.emit_event("assistant_state", {"paused": False})
            return {"ok": True, "paused": False}
        if command == "restart_runtime":
            self._restart_runtime()
            return {"ok": True, "state": self._state_payload()}
        if command == "handle_input":
            text = str(args.get("text", "")).strip()
            source = str(args.get("source", "chat")).strip() or "chat"
            return self._process_input(text, source=source)
        if command == "listen_voice":
            return self._listen_and_process()
        if command == "shutdown":
            self.shutdown()
            return {"ok": True, "shutdown": True}
        return {"ok": False, "error": f"unknown_command:{command}"}

    def emit_event(self, event: str, payload: dict[str, Any]) -> None:
        self._write({"type": "event", "event": event, "payload": payload})

    def emit_result(self, request_id: str | int | None, ok: bool, result: dict[str, Any]) -> None:
        self._write({"type": "result", "id": request_id, "ok": ok, "result": result})

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        try:
            self.wake_word.stop()
        except RuntimeError:
            self.emit_event("notification", {"title": "NIRA", "message": "Wake word shutdown reported an error.", "level": "warning"})
        with self._runtime_lock:
            runtime = self.runtime
            try:
                runtime.remove_status_listener(self._on_runtime_event)
            except Exception:
                pass
            runtime.shutdown()

    def _process_input(self, text: str, *, source: str) -> dict[str, Any]:
        if self._paused:
            return {"ok": False, "error": "assistant_paused"}
        if not text:
            return {"ok": False, "error": "missing_text"}
        self.emit_event("assistant_visual_state", {"state": "thinking", "source": source, "text": text})
        try:
            with self._runtime_lock:
                response = self.runtime.handle(text)
        except Exception as exc:
            self.emit_event("assistant_visual_state", {"state": "idle"})
            self.emit_event("notification", {"title": "NIRA", "message": str(exc), "level": "error"})
            return {"ok": False, "error": str(exc)}
        payload = self._response_payload(response, source=source)
        self.emit_event("response", payload)
        if response.task_results:
            self.emit_event(
                "notification",
                {"title": "NIRA", "message": "Task completed successfully", "level": "success"},
            )
        for anomaly in response.anomalies:
            self.emit_event("notification", {"title": "NIRA", "message": anomaly, "level": "warning"})
        if source == "voice":
            self.emit_event("assistant_visual_state", {"state": "speaking"})
            self.voice.speak(response.text)
        self.emit_event("assistant_visual_state", {"state": "idle"})
        return {"ok": True, "response": payload}

    def _listen_and_process(self) -> dict[str, Any]:
        if self._paused:
            return {"ok": False, "error": "assistant_paused"}
        self.emit_event("assistant_visual_state", {"state": "listening"})
        self.wake_word.stop()
        try:
            transcript = self.voice.listen_once()
            if not transcript:
                self.emit_event("assistant_visual_state", {"state": "idle"})
                wake_status = self.wake_word.start(self._on_wake_word_detected)
                return {"ok": False, "error": "voice_unavailable", "voice_status": self.voice.status(), "wake_word": asdict(wake_status)}
            self.emit_event("voice_transcript", {"text": transcript})
            return self._process_input(transcript, source="voice")
        finally:
            self.wake_word.start(self._on_wake_word_detected)

    def _state_payload(self) -> dict[str, Any]:
        with self._runtime_lock:
            runtime = self.runtime
            return {
                "paused": self._paused,
                "voice_status": self.voice.status(),
                "wake_word_status": asdict(self.wake_word.status),
                "system_metrics": runtime.system_metrics.snapshot(),
                "model_stats": runtime.model_manager.stats(),
                "model_registry": runtime.model_registry.to_mapping(),
            }

    def _response_payload(self, response: RuntimeResponse, *, source: str) -> dict[str, Any]:
        return {
            "source": source,
            "text": response.text,
            "plan": response.plan,
            "task_results": response.task_results,
            "anomalies": response.anomalies,
            "state": {
                "intent": response.state.intent,
                "context": response.state.context,
                "confidence": response.state.confidence,
                "risk_level": response.state.risk_level,
            },
        }

    def _on_runtime_event(self, event: dict[str, Any]) -> None:
        self.emit_event("runtime_status", event)

    def _on_wake_word_detected(self) -> None:
        self.emit_event(
            "wake_word_detected",
            {
                "keyword": self.wake_word.keyword,
                "timestamp": time.time(),
            },
        )

    def _heartbeat_loop(self) -> None:
        while not self._shutdown:
            time.sleep(5)
            if self._shutdown:
                break
            with self._runtime_lock:
                runtime = self.runtime
                system_metrics = runtime.system_metrics.snapshot()
                model_stats = runtime.model_manager.stats()
            self.emit_event(
                "heartbeat",
                {
                    "system_metrics": system_metrics,
                    "model_stats": model_stats,
                },
            )

    def _restart_runtime(self) -> None:
        with self._runtime_lock:
            old_runtime = self.runtime
            try:
                old_runtime.remove_status_listener(self._on_runtime_event)
            except Exception:
                pass
            old_runtime.shutdown()
            self.runtime = self._build_runtime()
            self.runtime.add_status_listener(self._on_runtime_event)

    def _write(self, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=True)
        with self._write_lock:
            self.output.write(line + "\n")
            self.output.flush()

    @staticmethod
    def _build_runtime() -> AgentRuntime:
        config = ConfigLoader().load()
        return AgentRuntime(config=config)


def main() -> int:
    service = DesktopBridgeService()
    try:
        service.serve_forever()
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
