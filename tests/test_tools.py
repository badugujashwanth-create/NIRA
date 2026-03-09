from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nira.tools.build_runner import BuildRunner
from nira.tools.dependency_manager import DependencyManager
from nira.tools.file_manager import FileManager, UpdateConfigTool
from nira.tools.project_analyzer import ProjectAnalyzer


class DummyState:
    user_input = "test"
    intent = {}

    def __init__(self, cwd: Path | None = None) -> None:
        self.context = {"cwd": str(cwd or Path.cwd())}


class ToolTests(unittest.TestCase):
    def test_file_manager_write_and_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "note.txt"
            manager = FileManager()
            state = DummyState(Path(tmp))
            self.assertTrue(manager.run({"action": "write", "path": str(path), "content": "hello"}, state).ok)
            read = manager.run({"action": "read", "path": str(path)}, state)
            self.assertIn("hello", read.output)

    def test_update_config_appends_setting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            tool = UpdateConfigTool()
            result = tool.run({"path": str(path), "setting": "MODE", "value": "local"}, DummyState(Path(tmp)))
            self.assertTrue(result.ok)
            self.assertIn("MODE=local", path.read_text(encoding="utf-8"))

    def test_dependency_manager_updates_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                temp_root = Path(tmp)
                (temp_root / "requirements.txt").write_text("", encoding="utf-8")
                import os

                os.chdir(temp_root)
                result = DependencyManager().run({"dependency": "requests", "version": "2.0.0"}, DummyState(temp_root))
                self.assertTrue(result.ok)
                self.assertIn("requests==2.0.0", (temp_root / "requirements.txt").read_text(encoding="utf-8"))
            finally:
                os.chdir(cwd)

    def test_project_analyzer_counts_python_files(self) -> None:
        result = ProjectAnalyzer().run({"path": "."}, DummyState(Path.cwd()))
        self.assertTrue(result.ok)
        self.assertIn("python_files", result.data)

    def test_build_runner_executes_command(self) -> None:
        result = BuildRunner(timeout_sec=10).run({"command": "python -c \"print('ok')\""}, DummyState(Path.cwd()))
        self.assertTrue(result.ok)
        self.assertIn("ok", result.output)


if __name__ == "__main__":
    unittest.main()
