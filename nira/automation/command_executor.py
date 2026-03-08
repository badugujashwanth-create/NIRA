from __future__ import annotations

import ctypes
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil

from nira.automation.undo_stack import UndoEntry


@dataclass
class CommandResult:
    success: bool
    message: str
    undo_entry: Optional[UndoEntry] = None


class CommandExecutor:
    APP_ALIASES = {
        "chrome": "chrome.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "explorer": "explorer.exe",
        "calculator": "calc.exe",
        "cmd": "cmd.exe",
        "powershell": "powershell.exe",
    }

    def open_app(self, app_name_or_path: str) -> CommandResult:
        target = app_name_or_path.strip().strip('"')
        if not target:
            return CommandResult(False, "No app name provided.")

        resolved = self._resolve_app_target(target)
        if not resolved:
            return CommandResult(False, f"Could not resolve application: {target}")

        try:
            process = subprocess.Popen([resolved], shell=False)
        except OSError as exc:
            return CommandResult(False, f"Failed to open app '{target}': {exc}")

        pid = process.pid

        def _undo() -> tuple[bool, str]:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=5)
                return True, f"Closed app opened by NIRA (PID {pid})."
            except Exception as exc:
                return False, f"Could not undo open_app for PID {pid}: {exc}"

        undo = UndoEntry(description=f"open_app:{target}", undoable=True, undo=_undo)
        return CommandResult(True, f"Opened {target}.", undo)

    def close_app(self, process_name: str) -> CommandResult:
        target = process_name.strip().lower().replace(".exe", "")
        if not target:
            return CommandResult(False, "No process name provided.")

        matched: list[int] = []
        for proc in psutil.process_iter(["pid", "name"]):
            name = (proc.info.get("name") or "").lower().replace(".exe", "")
            if target in name:
                try:
                    psutil.Process(proc.info["pid"]).terminate()
                    matched.append(proc.info["pid"])
                except Exception:
                    continue

        if not matched:
            return CommandResult(False, f"No matching process found for '{process_name}'.")

        undo = UndoEntry(
            description=f"close_app:{process_name}",
            undoable=False,
            undo=None,
        )
        return CommandResult(True, f"Closed {len(matched)} process(es) matching {process_name}.", undo)

    def create_folder(self, path: str) -> CommandResult:
        target = Path(path).expanduser()
        try:
            target.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            return CommandResult(False, f"Folder already exists: {target}")
        except OSError as exc:
            return CommandResult(False, f"Failed creating folder '{target}': {exc}")

        def _undo() -> tuple[bool, str]:
            try:
                if target.exists() and target.is_dir():
                    if any(target.iterdir()):
                        return False, f"Cannot remove '{target}' because it is not empty."
                    target.rmdir()
                    return True, f"Removed folder {target}."
                return False, f"Folder no longer exists: {target}"
            except OSError as exc:
                return False, f"Could not remove folder '{target}': {exc}"

        undo = UndoEntry(description=f"create_folder:{target}", undoable=True, undo=_undo)
        return CommandResult(True, f"Created folder: {target}", undo)

    def move_file(self, src: str, dst: str) -> CommandResult:
        source = Path(src).expanduser()
        destination = Path(dst).expanduser()
        if not source.exists():
            return CommandResult(False, f"Source file does not exist: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            final_path = Path(shutil.move(str(source), str(destination)))
        except OSError as exc:
            return CommandResult(False, f"Move failed: {exc}")

        def _undo() -> tuple[bool, str]:
            try:
                moved_back = Path(shutil.move(str(final_path), str(source)))
                return True, f"Moved file back to {moved_back}."
            except OSError as exc:
                return False, f"Could not move file back: {exc}"

        undo = UndoEntry(description=f"move_file:{source}->{destination}", undoable=True, undo=_undo)
        return CommandResult(True, f"Moved file to {final_path}", undo)

    def set_volume(self, percent: int) -> CommandResult:
        target = max(0, min(100, int(percent)))
        before = self._get_volume_percent()
        try:
            self._set_volume_percent(target)
        except OSError as exc:
            return CommandResult(False, f"Volume change failed: {exc}")

        def _undo() -> tuple[bool, str]:
            try:
                self._set_volume_percent(before)
                return True, f"Restored volume to {before}%."
            except OSError as exc:
                return False, f"Failed restoring volume: {exc}"

        undo = UndoEntry(description=f"set_volume:{target}", undoable=True, undo=_undo)
        return CommandResult(True, f"Volume set to {target}%.", undo)

    def execute_action(self, action: str, args: dict[str, object]) -> CommandResult:
        if action == "open_app":
            return self.open_app(str(args.get("target", "")))
        if action == "close_app":
            return self.close_app(str(args.get("target", "")))
        if action == "create_folder":
            return self.create_folder(str(args.get("path", "")))
        if action == "move_file":
            return self.move_file(str(args.get("src", "")), str(args.get("dst", "")))
        if action == "set_volume":
            return self.set_volume(int(args.get("percent", 0)))
        return CommandResult(False, f"Unknown automation action: {action}")

    def _resolve_app_target(self, target: str) -> Optional[str]:
        if Path(target).exists():
            return str(Path(target))
        alias_target = self.APP_ALIASES.get(target.lower(), target)
        candidate = alias_target
        if not candidate.lower().endswith(".exe") and "\\" not in candidate and "/" not in candidate:
            candidate = f"{candidate}.exe"
        resolved = shutil.which(candidate)
        return resolved or candidate

    def _get_volume_percent(self) -> int:
        volume = ctypes.c_ulong()
        result = ctypes.windll.winmm.waveOutGetVolume(0, ctypes.byref(volume))
        if result != 0:
            raise OSError("waveOutGetVolume failed")
        left = volume.value & 0xFFFF
        percent = int((left / 0xFFFF) * 100)
        return max(0, min(100, percent))

    def _set_volume_percent(self, percent: int) -> None:
        raw = int((max(0, min(100, percent)) / 100) * 0xFFFF)
        value = raw | (raw << 16)
        result = ctypes.windll.winmm.waveOutSetVolume(0, value)
        if result != 0:
            raise OSError("waveOutSetVolume failed")

