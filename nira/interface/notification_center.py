from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

try:
    from win10toast import ToastNotifier  # type: ignore
except Exception:
    ToastNotifier = None


@dataclass
class Notification:
    title: str
    message: str
    level: str = "info"
    created_at: float = field(default_factory=time.time)


NotificationListener = Callable[[Notification], None]


class NotificationCenter:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.history: list[Notification] = []
        self._listeners: list[NotificationListener] = []
        self._toast = ToastNotifier() if enabled and ToastNotifier is not None else None

    def subscribe(self, listener: NotificationListener) -> None:
        self._listeners.append(listener)

    def notify(self, title: str, message: str, level: str = "info") -> Notification:
        notification = Notification(title=title, message=message, level=level)
        self.history.append(notification)
        if self.enabled:
            print(f"[{title}] {message}")
            if self._toast is not None:
                try:
                    self._toast.show_toast(title, message, threaded=True, duration=4)
                except Exception:
                    pass
        for listener in list(self._listeners):
            try:
                listener(notification)
            except Exception:
                continue
        return notification

    def info(self, title: str, message: str) -> Notification:
        return self.notify(title, message, level="info")

    def success(self, title: str, message: str) -> Notification:
        return self.notify(title, message, level="success")

    def warning(self, title: str, message: str) -> Notification:
        return self.notify(title, message, level="warning")

    def error(self, title: str, message: str) -> Notification:
        return self.notify(title, message, level="error")
