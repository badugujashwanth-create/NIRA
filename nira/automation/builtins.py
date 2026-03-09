from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Callable, Protocol, cast

import psutil

from nira.automation.models import ExecutedAction, ToolResult
from nira.core.path_utils import PathSecurityError, resolve_within_root, validate_public_http_url


logger = logging.getLogger(__name__)

ToolArgs = dict[str, object]
ExecutorResult = tuple[ToolResult, ExecutedAction | None]
WorkflowRunner = Callable[[str], ToolResult]


class _TesseractLike(Protocol):
    def image_to_string(self, image: object) -> str: ...


class BuiltinExecutors:
    def __init__(self) -> None:
        self._workflow_runner: WorkflowRunner | None = None

    def set_workflow_runner(self, runner: WorkflowRunner) -> None:
        self._workflow_runner = runner

    def open_app(self, args: ToolArgs) -> ExecutorResult:
        target = str(args.get("target", "")).strip().strip('"')
        if not target:
            return ToolResult(False, "Missing app target."), None
        try:
            command = shlex.split(target, posix=False)
            if not command:
                return ToolResult(False, "Missing app target."), None
            proc = subprocess.Popen(command, shell=False)
        except (ValueError, OSError) as exc:
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

        action: ExecutedAction = ExecutedAction(
            description=f"open_app:{target}",
            undoable=True,
            undo_fn=_undo,
        )
        return ToolResult(True, f"Opened {target}."), action

    def close_app(self, args: ToolArgs) -> ExecutorResult:
        process_name = str(args.get("process_name", "")).strip().lower().replace(".exe", "")
        if not process_name:
            return ToolResult(False, "Missing process_name."), None
        killed = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower().replace(".exe", "")
                if process_name in name:
                    pid = proc.info.get("pid")
                    if not isinstance(pid, int):
                        continue
                    psutil.Process(pid).terminate()
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

    def create_folder(self, args: ToolArgs) -> ExecutorResult:
        raw_path = str(args.get("path", "")).strip().strip('"')
        if not raw_path:
            return ToolResult(False, "Missing path."), None
        try:
            folder = resolve_within_root(Path.cwd(), raw_path)
        except (PathSecurityError, OSError) as exc:
            return ToolResult(False, f"Invalid folder path: {exc}"), None
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

    def move_file(self, args: ToolArgs) -> ExecutorResult:
        try:
            src = resolve_within_root(Path.cwd(), str(args.get("src", "")).strip('"'), must_exist=True)
            dst = resolve_within_root(Path.cwd(), str(args.get("dst", "")).strip('"'))
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Invalid move paths: {exc}"), None
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

    def delete_file(self, args: ToolArgs) -> ExecutorResult:
        try:
            path = resolve_within_root(Path.cwd(), str(args.get("path", "")).strip('"'), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"File not found: {exc}"), None
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

    def open_url(self, args: ToolArgs) -> ExecutorResult:
        url = str(args.get("url", "")).strip()
        try:
            safe_url = validate_public_http_url(url)
            webbrowser.open(safe_url)
            return ToolResult(True, f"Opened URL: {safe_url}"), None
        except Exception as exc:
            return ToolResult(False, f"Browser open failed: {exc}"), None

    def take_screenshot(self, args: ToolArgs) -> ExecutorResult:
        try:
            output = resolve_within_root(Path.cwd(), str(args.get("path", "screenshot.png")))
        except (PathSecurityError, OSError) as exc:
            return ToolResult(False, f"Invalid screenshot path: {exc}"), None
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import ImageGrab  # type: ignore

            image = ImageGrab.grab()
            image.save(output)
            return ToolResult(True, f"Screenshot saved: {output}", {"path": str(output)}), None
        except Exception as exc:
            return ToolResult(False, f"Screenshot failed (install pillow): {exc}"), None

    def ocr_image(self, args: ToolArgs) -> ExecutorResult:
        try:
            path = resolve_within_root(Path.cwd(), str(args.get("path", "")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Image not found: {exc}"), None
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore

            tesseract = cast(_TesseractLike, pytesseract)
            image = cast(object, Image.open(path))
            text = tesseract.image_to_string(image).strip()
            if not text:
                return ToolResult(False, "OCR completed but no text recognized."), None
            return ToolResult(True, text, {"text": text}), None
        except Exception as exc:
            return ToolResult(False, f"OCR failed (install pillow + pytesseract + Tesseract OCR): {exc}"), None

    def run_workflow(self, args: ToolArgs) -> ExecutorResult:
        name = str(args.get("name", "")).strip()
        if not name:
            return ToolResult(False, "Missing workflow name."), None
        runner = self._workflow_runner
        if runner is None:
            return ToolResult(False, "Workflow runner is not configured."), None
        result: ToolResult = runner(name)
        return result, None

    def read_file(self, args: ToolArgs) -> ExecutorResult:
        try:
            path = resolve_within_root(Path.cwd(), str(args.get("path", "")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"File not found: {exc}"), None
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if len(text) > 8000:
                text = text[:8000] + "\n...[truncated]"
            return ToolResult(True, text, {"path": str(path)}), None
        except Exception as exc:
            return ToolResult(False, f"Read failed: {exc}"), None

    def write_file(self, args: ToolArgs) -> ExecutorResult:
        raw_path = str(args.get("path", "")).strip()
        if not raw_path:
            return ToolResult(False, "Missing file path."), None
        try:
            path = resolve_within_root(Path.cwd(), raw_path)
        except (PathSecurityError, OSError) as exc:
            return ToolResult(False, f"Invalid file path: {exc}"), None
        content = str(args.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        previous: str | None = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else None
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

    def list_directory(self, args: ToolArgs) -> ExecutorResult:
        try:
            path = resolve_within_root(Path.cwd(), str(args.get("path", ".")), must_exist=True)
        except (PathSecurityError, FileNotFoundError, OSError) as exc:
            return ToolResult(False, f"Directory not found: {exc}"), None
        if not path.is_dir():
            return ToolResult(False, f"Directory not found: {path}"), None
        try:
            entries: list[str] = [item.name for item in path.iterdir()]
            preview = "\n".join(entries[:200])
            return ToolResult(True, preview or "(empty)", {"count": len(entries)}), None
        except Exception as exc:
            return ToolResult(False, f"List directory failed: {exc}"), None
