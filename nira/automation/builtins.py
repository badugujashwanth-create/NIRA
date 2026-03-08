from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable

import psutil

from nira_agent.automation.models import ExecutedAction, ToolResult


logger = logging.getLogger(__name__)


class BuiltinExecutors:
    def __init__(self) -> None:
        self._workflow_runner: Callable[[str], ToolResult] | None = None

    def set_workflow_runner(self, runner: Callable[[str], ToolResult]) -> None:
        self._workflow_runner = runner

    def open_app(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        target = str(args.get("target", "")).strip().strip('"')
        if not target:
            return ToolResult(False, "Missing app target."), None
        try:
            proc = subprocess.Popen(target, shell=True)
        except Exception as exc:
            return ToolResult(False, f"Failed to open app '{target}': {exc}"), None

        pid = proc.pid

        def _undo() -> ToolResult:
            try:
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=5)
                return ToolResult(True, f"Closed app PID {pid}.")
            except Exception as exc:  # pragma: no cover - runtime dependent
                return ToolResult(False, f"Failed undo for PID {pid}: {exc}")

        action = ExecutedAction(
            description=f"open_app:{target}",
            undoable=True,
            undo_fn=_undo,
        )
        return ToolResult(True, f"Opened {target}."), action

    def close_app(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        process_name = str(args.get("process_name", "")).strip().lower().replace(".exe", "")
        if not process_name:
            return ToolResult(False, "Missing process_name."), None
        killed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower().replace(".exe", "")
                if process_name in name:
                    psutil.Process(proc.info["pid"]).terminate()
                    killed += 1
            except Exception:
                continue
        if killed == 0:
            return ToolResult(False, f"No process matched '{process_name}'."), None
        return ToolResult(True, f"Terminated {killed} process(es) for {process_name}."), ExecutedAction(
            description=f"close_app:{process_name}",
            undoable=False,
            undo_fn=None,
        )

    def create_folder(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        folder = Path(str(args.get("path", "")).strip('"')).expanduser()
        if not str(folder):
            return ToolResult(False, "Missing path."), None
        try:
            folder.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            return ToolResult(False, f"Folder already exists: {folder}"), None
        except Exception as exc:
            return ToolResult(False, f"Could not create folder: {exc}"), None

        def _undo() -> ToolResult:
            try:
                if any(folder.iterdir()):
                    return ToolResult(False, "Folder is not empty; cannot undo.")
                folder.rmdir()
                return ToolResult(True, f"Removed folder {folder}.")
            except Exception as exc:
                return ToolResult(False, f"Undo failed: {exc}")

        return ToolResult(True, f"Created folder: {folder}"), ExecutedAction(
            description=f"create_folder:{folder}",
            undoable=True,
            undo_fn=_undo,
        )

    def move_file(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        src = Path(str(args.get("src", "")).strip('"')).expanduser()
        dst = Path(str(args.get("dst", "")).strip('"')).expanduser()
        if not src.exists():
            return ToolResult(False, f"Source not found: {src}"), None
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            moved = Path(shutil.move(str(src), str(dst)))
        except Exception as exc:
            return ToolResult(False, f"Move failed: {exc}"), None

        def _undo() -> ToolResult:
            try:
                shutil.move(str(moved), str(src))
                return ToolResult(True, f"Moved file back to {src}.")
            except Exception as exc:
                return ToolResult(False, f"Undo failed: {exc}")

        return ToolResult(True, f"Moved file to {moved}."), ExecutedAction(
            description=f"move_file:{src}->{dst}",
            undoable=True,
            undo_fn=_undo,
        )

    def delete_file(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        path = Path(str(args.get("path", "")).strip('"')).expanduser()
        if not path.exists():
            return ToolResult(False, f"File not found: {path}"), None
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            return ToolResult(True, f"Deleted {path}."), ExecutedAction(
                description=f"delete_file:{path}",
                undoable=False,
                undo_fn=None,
            )
        except Exception as exc:
            return ToolResult(False, f"Delete failed: {exc}"), None

    def open_url(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        url = str(args.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            return ToolResult(False, "URL must start with http:// or https://"), None
        try:
            webbrowser.open(url)
            return ToolResult(True, f"Opened URL: {url}"), None
        except Exception as exc:
            return ToolResult(False, f"Browser open failed: {exc}"), None

    def take_screenshot(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        output = Path(str(args.get("path", "screenshot.png"))).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import ImageGrab  # type: ignore

            image = ImageGrab.grab()
            image.save(output)
            return ToolResult(True, f"Screenshot saved: {output}", {"path": str(output)}), None
        except Exception as exc:
            return ToolResult(False, f"Screenshot failed (install pillow): {exc}"), None

    def ocr_image(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        path = Path(str(args.get("path", ""))).expanduser()
        if not path.exists():
            return ToolResult(False, f"Image not found: {path}"), None
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            text = pytesseract.image_to_string(Image.open(path))
            text = text.strip()
            if not text:
                return ToolResult(False, "OCR completed but no text recognized."), None
            return ToolResult(True, text, {"text": text}), None
        except Exception as exc:
            return ToolResult(False, f"OCR failed (install pillow + pytesseract + Tesseract OCR): {exc}"), None

    def run_workflow(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        name = str(args.get("name", "")).strip()
        if not name:
            return ToolResult(False, "Missing workflow name."), None
        if not self._workflow_runner:
            return ToolResult(False, "Workflow runner is not configured."), None
        result = self._workflow_runner(name)
        return result, None

    def read_file(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        path = Path(str(args.get("path", ""))).expanduser()
        if not path.exists():
            return ToolResult(False, f"File not found: {path}"), None
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if len(text) > 8000:
                text = text[:8000] + "\n...[truncated]"
            return ToolResult(True, text, {"path": str(path)}), None
        except Exception as exc:
            return ToolResult(False, f"Read failed: {exc}"), None

    def write_file(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        path = Path(str(args.get("path", ""))).expanduser()
        content = str(args.get("content", ""))
        if not path:
            return ToolResult(False, "Missing file path."), None
        path.parent.mkdir(parents=True, exist_ok=True)
        previous = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as exc:
            return ToolResult(False, f"Write failed: {exc}"), None

        def _undo() -> ToolResult:
            try:
                if previous is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.write_text(previous, encoding="utf-8")
                return ToolResult(True, f"Reverted write for {path}.")
            except Exception as exc:
                return ToolResult(False, f"Undo write failed: {exc}")

        return ToolResult(True, f"Wrote file: {path}"), ExecutedAction(
            description=f"write_file:{path}",
            undoable=True,
            undo_fn=_undo,
        )

    def list_directory(self, args: dict[str, object]) -> tuple[ToolResult, ExecutedAction | None]:
        path = Path(str(args.get("path", "."))).expanduser()
        if not path.exists() or not path.is_dir():
            return ToolResult(False, f"Directory not found: {path}"), None
        try:
            entries = [item.name for item in path.iterdir()]
            preview = "\n".join(entries[:200])
            return ToolResult(True, preview or "(empty)", {"count": len(entries)}), None
        except Exception as exc:
            return ToolResult(False, f"List directory failed: {exc}"), None

