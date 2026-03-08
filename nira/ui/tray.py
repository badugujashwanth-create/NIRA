from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QIcon, QPainter, QPixmap, QColor
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon


def _startup_script_path() -> Path:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "NIRA.cmd"
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "NIRA.cmd"


def is_startup_enabled() -> bool:
    return _startup_script_path().exists()


def set_startup_enabled(enabled: bool, project_root: Path) -> tuple[bool, str]:
    startup_file = _startup_script_path()
    try:
        if enabled:
            startup_file.parent.mkdir(parents=True, exist_ok=True)
            python_exe = Path(sys.executable)
            script = (
                "@echo off\n"
                f'cd /d "{project_root}"\n'
                f'"{python_exe}" -m nira\n'
            )
            startup_file.write_text(script, encoding="utf-8")
            return True, f"Startup enabled ({startup_file})."
        if startup_file.exists():
            startup_file.unlink()
        return True, "Startup disabled."
    except OSError as exc:
        return False, f"Could not update startup setting: {exc}"


def build_default_icon() -> QIcon:
    pix = QPixmap(32, 32)
    pix.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setBrush(QColor(52, 142, 255))
    painter.setPen(QColor(210, 240, 255))
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QIcon(pix)


class NiraTray(QObject):
    mic_toggled = pyqtSignal(bool)
    click_through_toggled = pyqtSignal(bool)
    dnd_toggled = pyqtSignal(bool)
    startup_toggled = pyqtSignal(bool)
    undo_requested = pyqtSignal()
    listen_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(
        self,
        mic_enabled: bool,
        click_through_enabled: bool,
        dnd_enabled: bool,
        startup_enabled: bool,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(build_default_icon())
        self.tray.setToolTip("NIRA")
        self.menu = QMenu()

        self.action_mic = QAction("Enable Microphone", self.menu)
        self.action_mic.setCheckable(True)
        self.action_mic.setChecked(mic_enabled)
        self.action_mic.triggered.connect(self.mic_toggled.emit)
        self.menu.addAction(self.action_mic)

        self.action_click = QAction("Enable Click-Through", self.menu)
        self.action_click.setCheckable(True)
        self.action_click.setChecked(click_through_enabled)
        self.action_click.triggered.connect(self.click_through_toggled.emit)
        self.menu.addAction(self.action_click)

        self.action_dnd = QAction("Do Not Disturb", self.menu)
        self.action_dnd.setCheckable(True)
        self.action_dnd.setChecked(dnd_enabled)
        self.action_dnd.triggered.connect(self.dnd_toggled.emit)
        self.menu.addAction(self.action_dnd)

        self.action_startup = QAction("Start With Windows", self.menu)
        self.action_startup.setCheckable(True)
        self.action_startup.setChecked(startup_enabled)
        self.action_startup.triggered.connect(self.startup_toggled.emit)
        self.menu.addAction(self.action_startup)

        self.menu.addSeparator()

        self.action_listen = QAction("Push-To-Talk Now", self.menu)
        self.action_listen.triggered.connect(self.listen_requested.emit)
        self.menu.addAction(self.action_listen)

        self.action_undo = QAction("Undo Last Action", self.menu)
        self.action_undo.triggered.connect(self.undo_requested.emit)
        self.menu.addAction(self.action_undo)

        self.menu.addSeparator()

        self.action_quit = QAction("Quit", self.menu)
        self.action_quit.triggered.connect(self.quit_requested.emit)
        self.menu.addAction(self.action_quit)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

    def show_message(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 2500)

    def set_mic_label(self, enabled: bool, details: str = "") -> None:
        label = "Enable Microphone"
        if not enabled:
            label = "Enable Microphone (disabled)"
        if details:
            label = f"{label} [{details}]"
        self.action_mic.setText(label)
