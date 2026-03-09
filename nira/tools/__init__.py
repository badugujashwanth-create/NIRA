from nira.tools.base import Tool, ToolResult
from nira.tools.browser_controller import BrowserController
from nira.tools.build_runner import BuildRunner
from nira.tools.code_generator import CodeGenerator
from nira.tools.dependency_manager import DependencyManager
from nira.tools.document_editor import DocumentEditorTool
from nira.tools.download_manager import DownloadManager
from nira.tools.file_manager import FileManager, UpdateConfigTool
from nira.tools.project_analyzer import ProjectAnalyzer
from nira.tools.registry import ToolRegistry
from nira.tools.research_tools import (
    AnalyzeSourcesTool,
    GenerateResearchReportTool,
    StoreKnowledgeTool,
    SummarizeInformationTool,
    TopicPlanningTool,
)


def build_default_registry(
    *,
    model,
    config,
    source_analyzer,
    report_generator,
    document_editor,
    topic_planner,
    summarizer,
    research_memory,
    vector_store,
    knowledge_graph,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(FileManager())
    registry.register(ProjectAnalyzer())
    registry.register(DependencyManager())
    registry.register(UpdateConfigTool())
    registry.register(CodeGenerator(model=model))
    registry.register(BuildRunner(timeout_sec=config.build_timeout_sec))
    registry.register(BrowserController(source_analyzer=source_analyzer, web_enabled=config.web_research_enabled))
    registry.register(DownloadManager(web_enabled=config.web_research_enabled))
    registry.register(DocumentEditorTool(document_editor=document_editor, report_generator=report_generator))
    registry.register(TopicPlanningTool(topic_planner))
    registry.register(AnalyzeSourcesTool(source_analyzer))
    registry.register(SummarizeInformationTool(summarizer))
    registry.register(GenerateResearchReportTool(report_generator))
    registry.register(StoreKnowledgeTool(research_memory, vector_store, knowledge_graph))
    return registry


__all__ = [
    "Tool",
    "ToolRegistry",
    "ToolResult",
    "build_default_registry",
]
