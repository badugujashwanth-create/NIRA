from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt5.QtCore import QObject, QTimer, pyqtSignal


@dataclass
class AnimationFrame:
    scale: float
    spin_angle: float
    x_offset: int
    glow_strength: float


class OrbAnimationController(QObject):
    frame_updated = pyqtSignal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = "idle"
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def set_state(self, state: str) -> None:
        self.state = state
        self._tick = 0

    def _on_tick(self) -> None:
        self._tick += 1
        t = self._tick / 30.0

        if self.state == "idle":
            frame = AnimationFrame(
                scale=1.0 + 0.03 * math.sin(t),
                spin_angle=(t * 20) % 360,
                x_offset=0,
                glow_strength=0.5 + 0.1 * math.sin(t),
            )
        elif self.state == "listening":
            frame = AnimationFrame(
                scale=1.0 + 0.08 * math.sin(t * 3.0),
                spin_angle=(t * 80) % 360,
                x_offset=0,
                glow_strength=0.8,
            )
        elif self.state == "thinking":
            frame = AnimationFrame(
                scale=1.0 + 0.05 * math.sin(t * 2.0),
                spin_angle=(t * 220) % 360,
                x_offset=0,
                glow_strength=0.9,
            )
        elif self.state == "speaking":
            frame = AnimationFrame(
                scale=1.0 + 0.06 * math.sin(t * 4.0),
                spin_angle=(t * 50) % 360,
                x_offset=0,
                glow_strength=0.85,
            )
        elif self.state == "error":
            frame = AnimationFrame(
                scale=1.0 + 0.1 * math.sin(t * 6.0),
                spin_angle=(t * 40) % 360,
                x_offset=int(4 * math.sin(t * 14.0)),
                glow_strength=1.0,
            )
        else:
            frame = AnimationFrame(scale=1.0, spin_angle=0.0, x_offset=0, glow_strength=0.6)

        self.frame_updated.emit(frame)

