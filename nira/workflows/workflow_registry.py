from __future__ import annotations

import json
from pathlib import Path


class WorkflowRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def register(self, name: str, steps: list[str], metadata: dict[str, object] | None = None) -> None:
        payload = self.load_all()
        payload[name] = {"steps": steps, "metadata": metadata or {}}
        self.path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def load_all(self) -> dict[str, object]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = self.path.with_suffix(f"{self.path.suffix}.invalid.bak")
            backup.write_text(self.path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
            self.path.write_text("{}", encoding="utf-8")
            return {}

    def ensure_builtin_workflows(self) -> None:
        payload = self.load_all()
        payload.setdefault(
            "research_topic",
            {
                "steps": [
                    "plan_topic",
                    "analyze_sources",
                    "summarize_information",
                    "generate_report",
                    "store_knowledge",
                ],
                "metadata": {"kind": "research"},
            },
        )
        self.path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    def suggest_name(self, trace: list[str]) -> str:
        if trace[:3] == ["git_pull", "install_deps", "run_server"]:
            return "start_project"
        if trace[:5] == [
            "plan_topic",
            "analyze_sources",
            "summarize_information",
            "generate_report",
            "store_knowledge",
        ]:
            return "research_topic"
        return "_".join(trace[:3]).replace("-", "_") or "workflow"
