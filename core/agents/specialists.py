from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.knowledge import KnowledgeBase
from core.research import ResearchAgent, ResearchSummary
from plugins.manager import PluginManager


@dataclass(slots=True)
class AgentResult:
    agent: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationAgent:
    def __init__(self, knowledge_base: KnowledgeBase, plugin_manager: PluginManager) -> None:
        self.knowledge_base = knowledge_base
        self.plugin_manager = plugin_manager

    async def handle(self, goal: str, context: dict[str, Any]) -> AgentResult:
        plugin_result = self.plugin_manager.try_execute(goal) if context.get("allow_plugins", True) else None
        if plugin_result is not None:
            return AgentResult(agent="conversation", output=plugin_result.text, metadata={"plugin": plugin_result.plugin})

        if isinstance(context.get("research_summary"), ResearchSummary):
            summary = context["research_summary"].summary
            return AgentResult(agent="conversation", output=summary, metadata={"sources": context["research_summary"].metadata})

        executions = context.get("executions", [])
        non_conversation_outputs = [
            execution.output
            for execution in executions
            if getattr(execution, "agent_name", "") != "conversation" and getattr(execution, "output", "")
        ]
        if non_conversation_outputs:
            return AgentResult(
                agent="conversation",
                output=f"Goal complete. {non_conversation_outputs[-1]}",
                metadata={"execution_steps": len(executions)},
            )

        matches = self.knowledge_base.search(goal, limit=2)
        if matches:
            output = " ".join(match.content for match in matches)
            return AgentResult(agent="conversation", output=output, metadata={"knowledge_hits": len(matches)})

        return AgentResult(agent="conversation", output=f"NIRA understands the goal: {goal}")


class PlanningAgent:
    async def handle(self, goal: str, context: dict[str, Any]) -> AgentResult:
        return AgentResult(agent="planning", output=f"Planning progress recorded for: {goal}")


class ResearchWorkerAgent:
    def __init__(self, research_agent: ResearchAgent) -> None:
        self.research_agent = research_agent

    async def handle(self, goal: str, context: dict[str, Any]) -> AgentResult:
        if isinstance(context.get("research_summary"), ResearchSummary):
            research_summary = context["research_summary"]
            return AgentResult(
                agent="research",
                output=research_summary.summary,
                metadata={"research_summary": research_summary, "cached": True},
            )
        research_summary = await self.research_agent.research(goal)
        return AgentResult(
            agent="research",
            output=research_summary.summary,
            metadata={"research_summary": research_summary},
        )


class AutomationAgent:
    async def handle(self, goal: str, context: dict[str, Any]) -> AgentResult:
        lowered = goal.lower()
        if "schedule" in lowered and "calendar" in lowered:
            return AgentResult(
                agent="automation",
                output=f"Prepared a calendar scheduling workflow for: {goal}. Connect a calendar backend or plugin to execute it.",
            )
        if "open" in lowered or "launch" in lowered:
            return AgentResult(
                agent="automation",
                output=f"Prepared an application launch workflow for: {goal}. Connect a system automation backend to execute it.",
            )
        return AgentResult(
            agent="automation",
            output=f"Automation capability is available for this goal: {goal}",
        )


class MemoryAgent:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base

    async def handle(self, goal: str, context: dict[str, Any]) -> AgentResult:
        stored = 0
        research_summary = context.get("research_summary")
        if isinstance(research_summary, ResearchSummary):
            for finding in research_summary.findings:
                self.knowledge_base.add(
                    topic=goal,
                    content=f"{finding.title}: {finding.summary}",
                    source=finding.url,
                )
                stored += 1
            return AgentResult(agent="memory", output=f"Stored {stored} research findings.", metadata={"stored": stored})

        matches = self.knowledge_base.search(goal, limit=3)
        output = " ".join(match.content for match in matches) if matches else "No relevant knowledge found."
        return AgentResult(agent="memory", output=output, metadata={"knowledge_hits": len(matches)})
