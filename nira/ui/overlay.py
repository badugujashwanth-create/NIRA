from __future__ import annotations

import ctypes
from typing import Optional

from PyQt5.QtCore import QPoint, QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt5.QtWidgets import QLabel, QWidget

from nira.ui.animation import AnimationFrame, OrbAnimationController


class BubbleLabel(QLabel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__("", parent)
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QLabel {
                background-color: rgba(28, 32, 42, 220);
                color: #f5f8ff;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 12px;
            }
            """
        )
        self.setWordWrap(True)
        self.hide()


class OrbOverlay(QWidget):
    def __init__(self, always_on_top: bool = True, click_through: bool = False) -> None:
        flags = Qt.FramelessWindowHint | Qt.Tool
        if always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.resize(108, 108)
        self.move(200, 200)

        self._dragging = False
        self._drag_offset = QPoint()
        self._click_through_enabled = click_through
        self._state = "idle"
        self._frame = AnimationFrame(scale=1.0, spin_angle=0.0, x_offset=0, glow_strength=0.6)

        self._theme = {
            "base": QColor(48, 120, 255, 170),
            "core": QColor(110, 210, 255, 210),
            "ring": QColor(200, 240, 255, 230),
            "error_tint": QColor(255, 190, 130, 220),
        }

        self._bubble = BubbleLabel(self)
        self._bubble_timer = QTimer(self)
        self._bubble_timer.setSingleShot(True)
        self._bubble_timer.timeout.connect(self._bubble.hide)

        self._animator = OrbAnimationController(self)
        self._animator.frame_updated.connect(self._on_frame)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.apply_click_through(self._click_through_enabled)

    def set_state(self, state: str) -> None:
        self._state = state
        self._animator.set_state(state)

    def apply_click_through(self, enabled: bool) -> None:
        self._click_through_enabled = enabled
        if hasattr(ctypes, "windll"):
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style |= WS_EX_LAYERED
            if enabled:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def is_click_through_enabled(self) -> bool:
        return self._click_through_enabled

    def show_bubble(self, text: str, timeout_ms: int = 2800) -> None:
        if not text.strip():
            return
        self._bubble.setText(text.strip())
        self._bubble.adjustSize()
        margin = 10
        x = max(0, self.width() - self._bubble.width() + margin)
        y = -self._bubble.height() - margin
        self._bubble.move(x, y)
        self._bubble.show()
        self._bubble.raise_()
        self._bubble_timer.start(timeout_ms)

    def _on_frame(self, frame: AnimationFrame) -> None:
        self._frame = frame
        self.update()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if self._click_through_enabled:
            return
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._click_through_enabled:
            return
        if self._dragging and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = False

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        center = self.rect().center()
        radius = int(30 * self._frame.scale)
        center = QPoint(center.x() + self._frame.x_offset, center.y())

        glow_color = self._theme["base"]
        core_color = self._theme["core"]
        ring_color = self._theme["ring"]
        if self._state == "error":
            # Error mode uses a warmer tint and shake animation.
            core_color = self._theme["error_tint"]

        gradient = QRadialGradient(center, radius + 18)
        gradient.setColorAt(0.0, core_color)
        gradient.setColorAt(0.6, glow_color)
        gradient.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(center, radius + 16, radius + 16)

        painter.setBrush(core_color)
        painter.drawEllipse(center, radius, radius)

        pen = QPen(ring_color, 3)
        painter.setPen(pen)
        arc_rect = QRect(center.x() - (radius + 8), center.y() - (radius + 8), (radius + 8) * 2, (radius + 8) * 2)
        start_angle = int(self._frame.spin_angle * 16)
        span = 120 * 16 if self._state == "thinking" else 90 * 16
        painter.drawArc(arc_rect, start_angle, span)

