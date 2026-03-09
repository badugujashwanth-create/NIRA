from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nira.intelligence.intent_analyzer import IntentResult


@dataclass
class PlannedTask:
    task_id: str
    description: str
    tool: str
    dependencies: list[str] = field(default_factory=list)
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "tool": self.tool,
            "dependencies": list(self.dependencies),
            "args": dict(self.args),
        }


class Planner:
    def __init__(self, planner_agent) -> None:
        self.planner_agent = planner_agent

    def build_plan(
        self,
        goal: str,
        intent: IntentResult,
        context: dict[str, Any],
        memory_hits: dict[str, Any],
        guidance: str = "",
    ) -> list[PlannedTask]:
        if intent.kind == "coding":
            return self._coding_plan(goal, context)
        if intent.kind == "research_topic":
            return self._research_plan(goal, intent)
        if intent.kind == "document":
            return self._document_plan(goal)
        if intent.kind == "workflow":
            return self._workflow_plan(goal, memory_hits)
        return self._chat_plan(goal, guidance)

    @staticmethod
    def _coding_plan(goal: str, context: dict[str, Any]) -> list[PlannedTask]:
        manifests = context.get("manifests", ["README.md"])
        config_candidates = [item for item in manifests if item.lower() not in {"requirements.txt", "readme.md"}]
        target = config_candidates[0] if config_candidates else ".env"
        return [
            PlannedTask("1", "Inspect the project layout and manifests", "analyze_project", args={"path": "."}),
            PlannedTask("2", "Add or update required dependency entries", "add_dependency", dependencies=["1"]),
            PlannedTask(
                "3",
                "Update local configuration to support the feature",
                "update_config",
                dependencies=["2"],
                args={"path": target, "setting": "goal", "value": goal},
            ),
            PlannedTask(
                "4",
                "Generate or refine the code needed for the goal",
                "generate_code",
                dependencies=["3"],
                args={"instructions": goal},
            ),
            PlannedTask("5", "Run a local verification command or build", "run_build", dependencies=["4"], args={"cwd": "."}),
        ]

    @staticmethod
    def _research_plan(goal: str, intent: IntentResult) -> list[PlannedTask]:
        return [
            PlannedTask("1", "Plan the research topic and subtopics", "plan_topic", args={"query": goal}),
            PlannedTask("2", "Collect and analyze research sources", "analyze_sources", dependencies=["1"], args={"query": goal, "use_web": intent.needs_web}),
            PlannedTask("3", "Summarize the collected research information", "summarize_information", dependencies=["2"]),
            PlannedTask("4", "Generate the structured research report", "generate_report", dependencies=["1", "2", "3"]),
            PlannedTask("5", "Store the research knowledge permanently", "store_knowledge", dependencies=["1", "2", "3", "4"]),
        ]

    @staticmethod
    def _document_plan(goal: str) -> list[PlannedTask]:
        return [
            PlannedTask("1", "Create or update the target document", "edit_document", args={"path": "document.md", "content": f"# Draft\n\n{goal}\n"}),
            PlannedTask("2", "Inspect the repository for related context", "analyze_project", dependencies=["1"], args={"path": "."}),
        ]

    @staticmethod
    def _workflow_plan(goal: str, memory_hits: dict[str, Any]) -> list[PlannedTask]:
        return [
            PlannedTask("1", "Inspect repeated local workflow patterns", "analyze_project", args={"path": "."}),
            PlannedTask("2", "Save workflow notes locally", "edit_document", dependencies=["1"], args={"content": f"workflow candidate for: {goal}\nexisting={memory_hits.get('workflow_memory', [])}"}),
        ]

    @staticmethod
    def _chat_plan(goal: str, guidance: str) -> list[PlannedTask]:
        return [PlannedTask("1", "Capture reasoning notes for the request", "edit_document", args={"path": "chat_notes.md", "content": f"{goal}\n\n{guidance}".strip()})]
