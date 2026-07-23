from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nira.tools.build_runner import BuildRunner
from nira.tools.dependency_manager import DependencyManager
from nira.tools.file_manager import FileManager, UpdateConfigTool
from nira.tools.project_analyzer import ProjectAnalyzer
from nira.tools.workspace_search import WorkspaceSearch


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

    def test_file_manager_bounds_large_read_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.txt"
            path.write_text("x" * 200, encoding="utf-8")
            read = FileManager().run(
                {"action": "read", "path": str(path), "max_bytes": 32},
                DummyState(Path(tmp)),
            )
            self.assertTrue(read.ok)
            self.assertTrue(read.data["truncated"])
            self.assertEqual(read.data["max_bytes"], 32)
            self.assertIn("Output truncated", read.output)

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

    def test_project_analyzer_excludes_dependency_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('app')", encoding="utf-8")
            (root / ".venv").mkdir()
            (root / ".venv" / "dependency.py").write_text("print('dependency')", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "library.js").write_text("export default {}", encoding="utf-8")

            result = ProjectAnalyzer().run({"path": "."}, DummyState(root))

            self.assertTrue(result.ok)
            self.assertEqual(result.data["python_files"], 1)
            self.assertEqual(result.data["languages"], {"Python": 1})

    def test_build_runner_executes_allowlisted_profile(self) -> None:
        result = BuildRunner(timeout_sec=10).run({"profile": "python_compile"}, DummyState(Path.cwd()))
        self.assertTrue(result.ok)
        self.assertTrue(result.data["verified"])

    def test_build_runner_rejects_arbitrary_command(self) -> None:
        result = BuildRunner(timeout_sec=10).run(
            {"profile": "shell", "command": "python -c \"print('unsafe')\""},
            DummyState(Path.cwd()),
        )
        self.assertFalse(result.ok)
        self.assertFalse(result.data["arbitrary_commands_allowed"])

    def test_workspace_search_is_bounded_and_excludes_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("# TODO: verify this\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "hidden.js").write_text("// TODO hidden\n", encoding="utf-8")
            result = WorkspaceSearch().run(
                {"query": "TODO", "max_matches": 5},
                DummyState(root),
            )
            self.assertTrue(result.ok)
            self.assertEqual(result.data["match_count"], 1)
            self.assertEqual(result.data["matches"][0]["path"], "app.py")


if __name__ == "__main__":
    unittest.main()
