from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import Dict

import psutil
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

try:
    import win32gui
    import win32process

    WIN32_AVAILABLE = True
except Exception:
    WIN32_AVAILABLE = False


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


@dataclass
class ActivitySnapshot:
    timestamp: float
    window_title: str
    process_name: str
    idle_seconds: float
    cpu_percent: float
    cpu_spike: bool
    current_app_duration: float


class ActivityTracker(QObject):
    snapshot_ready = pyqtSignal(object)

    def __init__(self, interval_sec: int = 5, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, interval_sec) * 1000)
        self._timer.timeout.connect(self._sample)
        self._last_process = ""
        self._last_switch_ts = time.time()
        self._durations: Dict[str, float] = {}
        psutil.cpu_percent(interval=None)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def get_durations(self) -> dict[str, float]:
        return dict(self._durations)

    def _sample(self) -> None:
        now = time.time()
        title, proc_name = self._get_foreground_window_info()
        if proc_name != self._last_process:
            elapsed = now - self._last_switch_ts
            if self._last_process:
                self._durations[self._last_process] = self._durations.get(self._last_process, 0.0) + elapsed
            self._last_process = proc_name
            self._last_switch_ts = now
            current_duration = 0.0
        else:
            current_duration = now - self._last_switch_ts

        cpu_percent = psutil.cpu_percent(interval=None)
        snapshot = ActivitySnapshot(
            timestamp=now,
            window_title=title,
            process_name=proc_name,
            idle_seconds=self._get_idle_seconds(),
            cpu_percent=cpu_percent,
            cpu_spike=cpu_percent >= 85.0,
            current_app_duration=current_duration,
        )
        self.snapshot_ready.emit(snapshot)

    def _get_foreground_window_info(self) -> tuple[str, str]:
        if not WIN32_AVAILABLE:
            return "", ""
        try:
            hwnd = win32gui.GetForegroundWindow()
            title = win32gui.GetWindowText(hwnd) or ""
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name()
            return title, proc_name
        except Exception:
            return "", ""

    def _get_idle_seconds(self) -> float:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)) == 0:
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, millis / 1000.0)
