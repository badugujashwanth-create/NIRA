from __future__ import annotations

import ctypes
import threading
import time
from dataclasses import dataclass
from typing import Callable

try:
    import win32gui
    import win32process
except Exception:  # pragma: no cover - optional dependency runtime
    win32gui = None
    win32process = None

import psutil


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


@dataclass
class ActivityEvent:
    ts: float
    active_window_title: str
    active_process_name: str
    idle_seconds: float
    cpu_percent: float


class ActivityTracker:
    def __init__(self, interval_sec: int = 5) -> None:
        self.interval_sec = max(1, interval_sec)
        self._callbacks: list[Callable[[ActivityEvent], None]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        psutil.cpu_percent(interval=None)

    def subscribe(self, callback: Callable[[ActivityEvent], None]) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            event = ActivityEvent(
                ts=time.time(),
                active_window_title=self._active_window_title(),
                active_process_name=self._active_process_name(),
                idle_seconds=self._idle_seconds(),
                cpu_percent=psutil.cpu_percent(interval=None),
            )
            for cb in list(self._callbacks):
                try:
                    cb(event)
                except Exception:
                    continue
            self._stop.wait(self.interval_sec)

    def _active_window_title(self) -> str:
        if win32gui is None:
            return ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return ""

    def _active_process_name(self) -> str:
        if win32gui is None or win32process is None:
            return ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name()
        except Exception:
            return ""

    def _idle_seconds(self) -> float:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)) == 0:
            return 0.0
        elapsed_ms = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, elapsed_ms / 1000.0)

