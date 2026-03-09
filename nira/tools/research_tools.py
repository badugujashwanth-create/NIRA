from __future__ import annotations

from typing import Any

from nira.memory.research_memory import ResearchEntry
from nira.tools.base import Tool, ToolResult


def _context(state) -> dict[str, Any]:
    context = getattr(state, "context", None)
    if not isinstance(context, dict):
        context = {}
        state.context = context
    return context


def _tool_output(state, key: str) -> dict[str, Any]:
    return dict(_context(state).get("task_outputs", {}).get(key, {}))


class TopicPlanningTool(Tool):
    name = "plan_topic"
    description = "Break a research request into topic, subtopics, and questions."

    def __init__(self, topic_planner) -> None:
        self.topic_planner = topic_planner

    def run(self, args: dict[str, Any], state) -> ToolResult:
        query = str(args.get("query") or state.user_input).strip()
        plan = self.topic_planner.plan(query)
        _context(state)["research_plan"] = plan.to_dict()
        return ToolResult(True, f"Planned research topic {plan.topic}", plan.to_dict())


class AnalyzeSourcesTool(Tool):
    name = "analyze_sources"
    description = "Collect local research text and extract key concepts and findings."

    def __init__(self, source_analyzer) -> None:
        self.source_analyzer = source_analyzer

    def run(self, args: dict[str, Any], state) -> ToolResult:
        plan_output = _tool_output(state, "plan_topic").get("data", {})
        query = str(args.get("query") or plan_output.get("topic") or state.user_input).strip()
        source_paths = args.get("source_paths") or _context(state).get("source_paths") or []
        analysis = self.source_analyzer.analyze(
            query=query,
            use_web=bool(args.get("use_web", False)),
            source_paths=list(source_paths),
        )
        if plan_output.get("subtopics"):
            fallback = [str(item) for item in plan_output.get("subtopics", []) if str(item).strip()]
            concepts = []
            concepts.extend(item for item in fallback if item not in concepts)
            concepts.extend(item for item in analysis.key_concepts if item and len(item) > 2 and item not in concepts)
            analysis.key_concepts = concepts[:8]
        _context(state)["source_analysis"] = analysis.to_dict()
        return ToolResult(analysis.ok, analysis.summary, analysis.to_dict())


class SummarizeInformationTool(Tool):
    name = "summarize_information"
    description = "Summarize collected research text and compress it for storage."

    def __init__(self, summarizer) -> None:
        self.summarizer = summarizer

    def run(self, args: dict[str, Any], state) -> ToolResult:
        analysis_data = _tool_output(state, "analyze_sources").get("data", {})
        topic = analysis_data.get("topic") or state.user_input
        text = str(analysis_data.get("collected_text") or args.get("text") or "")
        result = self.summarizer.summarize(text, topic=str(topic))
        _context(state)["summary_result"] = result.to_dict()
        return ToolResult(True, result.summary, result.to_dict())


class GenerateResearchReportTool(Tool):
    name = "generate_report"
    description = "Generate and persist a structured research report."

    def __init__(self, report_generator) -> None:
        self.report_generator = report_generator

    def run(self, args: dict[str, Any], state) -> ToolResult:
        plan_data = _tool_output(state, "plan_topic").get("data", {})
        analysis_data = _tool_output(state, "analyze_sources").get("data", {})
        summary_data = _tool_output(state, "summarize_information").get("data", {})
        topic = str(plan_data.get("topic") or analysis_data.get("topic") or state.user_input).strip()
        report = self.report_generator.generate(
            topic=topic,
            overview=str(summary_data.get("summary") or analysis_data.get("summary") or ""),
            key_methods=list(analysis_data.get("key_concepts", [])),
            recommendations=list(summary_data.get("key_sections", []))[:4],
            references=list(analysis_data.get("references", [])),
        )
        _context(state)["research_report"] = report.to_dict()
        return ToolResult(True, f"Generated report at {report.path}", report.to_dict())


class StoreKnowledgeTool(Tool):
    name = "store_knowledge"
    description = "Store summarized research into persistent knowledge memory and vector memory."

    def __init__(self, research_memory, vector_store, knowledge_graph) -> None:
        self.research_memory = research_memory
        self.vector_store = vector_store
        self.knowledge_graph = knowledge_graph

    def run(self, args: dict[str, Any], state) -> ToolResult:
        plan_data = _tool_output(state, "plan_topic").get("data", {})
        analysis_data = _tool_output(state, "analyze_sources").get("data", {})
        summary_data = _tool_output(state, "summarize_information").get("data", {})
        report_data = _tool_output(state, "generate_report").get("data", {})
        topic = str(plan_data.get("topic") or state.user_input).strip()
        concepts = list(analysis_data.get("key_concepts", []))
        references = list(analysis_data.get("references", []))
        summary = str(summary_data.get("summary") or analysis_data.get("summary") or "")
        entry = ResearchEntry(
            topic=topic,
            summary=summary,
            concepts=concepts,
            references=references,
            report_path=str(report_data.get("path", "")),
        )
        self.research_memory.store(entry)
        self.vector_store.add_research_summary(topic, summary, concepts, references)
        self.knowledge_graph.add_research_entry(
            topic=topic,
            subtopics=list(plan_data.get("subtopics", [])),
            concepts=concepts,
            tools=["llama.cpp", "source_analyzer", "summarizer"],
        )
        _context(state)["research_entry"] = entry.to_dict()
        return ToolResult(True, f"Stored knowledge for {topic}", entry.to_dict())
