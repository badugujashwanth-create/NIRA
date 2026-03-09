from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReflectionReport:
    summary: str
    repair_hint: str = ""


class ReflectionEngine:
    def __init__(self, model) -> None:
        self.model = model

    def reflect(self, state, execution, guidance: str = "") -> ReflectionReport:
        intent_kind = state.intent.get("kind", "unknown")
        if execution.success:
            if intent_kind == "research_topic":
                report = state.context.get("research_report", {})
                entry = state.context.get("research_entry", {})
                topic = entry.get("topic") or report.get("title") or state.user_input
                concepts = ", ".join(entry.get("concepts", [])[:4])
                report_path = report.get("path", "")
                summary = f"Research complete for {topic}."
                if entry.get("summary"):
                    summary = f"{summary} {entry['summary']}"
                if concepts:
                    summary = f"{summary} Key concepts: {concepts}."
                if report_path:
                    summary = f"{summary} Report: {report_path}."
                return ReflectionReport(summary=summary)

            if intent_kind == "chat":
                research_hits = state.memory_hits.get("research_memory", [])
                if research_hits:
                    top = research_hits[0]
                    summary = str(top.get("summary", "")).strip() or "Stored knowledge retrieved."
                    concepts = ", ".join(top.get("concepts", [])[:4])
                    if concepts:
                        summary = f"{summary} Concepts: {concepts}."
                    return ReflectionReport(summary=summary)

            completed = sum(1 for result in execution.results if result.ok)
            summary = f"Intent `{intent_kind}` completed with {completed} successful task(s)."
            if guidance:
                summary = f"{summary} {guidance}".strip()
            return ReflectionReport(summary=summary)

        reason = execution.results[-1].output if execution.results else "no tool output"
        return ReflectionReport(
            summary=f"Execution stopped safely after a task failure: {reason}",
            repair_hint=f"Review the failing task `{execution.current_task}` and retry with narrower instructions.",
        )

    def suggest_repair(self, tool_name: str, args: dict[str, object], output: str) -> dict[str, object]:
        if tool_name == "run_build" and "command" not in args:
            repaired = dict(args)
            repaired["command"] = "python -m compileall ."
            return repaired
        if tool_name == "edit_document" and "path" not in args:
            repaired = dict(args)
            repaired["path"] = "recovered_document.md"
            return repaired
        return dict(args)
