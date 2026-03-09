from __future__ import annotations

import math
from typing import Callable

try:
    import tkinter as tk

    TK_AVAILABLE = True
except Exception:
    tk = None
    TK_AVAILABLE = False


class DesktopOverlay:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.available = TK_AVAILABLE
        self.root = None
        self.window = None
        self.canvas = None
        self._message_label = None
        self._processing = False
        self._pulse_step = 0.0
        self._pulse_job = None
        self._drag_start: tuple[int, int] | None = None
        self._window_start: tuple[int, int] | None = None
        self._click_callback: Callable[[], None] | None = None
        self._owns_root = False

    def attach_root(self, root) -> None:
        self.root = root

    def bind_open_chat(self, callback: Callable[[], None]) -> None:
        self._click_callback = callback

    def start(self) -> None:
        if not self.enabled or not self.available or self.window is not None or tk is None:
            return
        try:
            if self.root is None:
                self.root = tk.Tk()
                self.root.withdraw()
                self._owns_root = True
            self.window = tk.Toplevel(self.root)
        except Exception:
            self.available = False
            return
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        try:
            self.window.attributes("-alpha", 0.92)
        except Exception:
            pass
        self.window.configure(bg="#06121f")
        width = 118
        height = 136
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x_pos = max(12, screen_width - width - 24)
        y_pos = max(12, int(screen_height * 0.28))
        self.window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        shell = tk.Frame(self.window, bg="#081726", highlightbackground="#7dd3fc", highlightthickness=1, bd=0)
        shell.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(shell, width=90, height=82, bg="#081726", highlightthickness=0, bd=0)
        self.canvas.pack(padx=12, pady=(10, 4))
        self._message_label = tk.Label(
            shell,
            text="Nira",
            bg="#081726",
            fg="#dbeafe",
            font=("Segoe UI", 10, "bold"),
            wraplength=92,
            justify="center",
        )
        self._message_label.pack(padx=8, pady=(0, 10))
        for widget in (self.window, shell, self.canvas, self._message_label):
            widget.bind("<ButtonPress-1>", self._on_press)
            widget.bind("<B1-Motion>", self._on_drag)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>", lambda _event: self.restore())
            widget.bind("<Leave>", lambda _event: self.minimize())
        self._redraw()
        self.minimize()

    def show_message(self, text: str) -> None:
        if not self.enabled or not self.available or self.window is None or self._message_label is None:
            return
        body = text.strip() or "Nira"
        self._message_label.configure(text=body[:96])
        self.restore()

    def set_processing(self, processing: bool) -> None:
        self._processing = processing
        if not self.enabled or not self.available or self.window is None:
            return
        if processing:
            self.restore()
        self._schedule_redraw()

    def minimize(self) -> None:
        if self.window is None:
            return
        try:
            self.window.attributes("-alpha", 0.78)
        except Exception:
            pass

    def restore(self) -> None:
        if self.window is None:
            return
        try:
            self.window.attributes("-alpha", 0.95 if self._processing else 0.88)
        except Exception:
            pass

    def close(self) -> None:
        if self._pulse_job is not None and self.window is not None:
            try:
                self.window.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        if self.window is not None:
            self.window.destroy()
            self.window = None
        if self._owns_root and self.root is not None:
            self.root.destroy()
            self.root = None

    def _schedule_redraw(self) -> None:
        if self.window is None:
            return
        self._redraw()
        if self._pulse_job is not None:
            self.window.after_cancel(self._pulse_job)
            self._pulse_job = None
        if self._processing:
            self._pulse_job = self.window.after(110, self._animate)

    def _animate(self) -> None:
        self._pulse_step += 0.35
        self._redraw()
        if self.window is not None and self._processing:
            self._pulse_job = self.window.after(110, self._animate)
        else:
            self._pulse_job = None

    def _redraw(self) -> None:
        if self.canvas is None:
            return
        self.canvas.delete("all")
        pulse = 0.0 if not self._processing else (math.sin(self._pulse_step) + 1.0) * 0.5
        glow = 12 + int(pulse * 10)
        radius = 22 + int(pulse * 4)
        self.canvas.create_oval(45 - glow, 40 - glow, 45 + glow, 40 + glow, fill="#16334a", outline="")
        self.canvas.create_oval(45 - radius, 40 - radius, 45 + radius, 40 + radius, fill="#38bdf8", outline="")
        self.canvas.create_oval(45 - 18, 40 - 18, 45 + 18, 40 + 18, fill="#e0f2fe", outline="")
        self.canvas.create_text(45, 40, text="N", fill="#082f49", font=("Segoe UI", 18, "bold"))

    def _on_press(self, event) -> None:
        if self.window is None:
            return
        self._drag_start = (event.x_root, event.y_root)
        self._window_start = (self.window.winfo_x(), self.window.winfo_y())

    def _on_drag(self, event) -> None:
        if self.window is None or self._drag_start is None or self._window_start is None:
            return
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        self.window.geometry(f"+{self._window_start[0] + dx}+{self._window_start[1] + dy}")

    def _on_release(self, event) -> None:
        if self.window is None or self._drag_start is None or self._window_start is None:
            return
        moved = abs(event.x_root - self._drag_start[0]) + abs(event.y_root - self._drag_start[1])
        self._drag_start = None
        self._window_start = None
        if moved < 6 and self._click_callback is not None:
            self._click_callback()
