from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from config.logger import get_logger
from config.settings import Settings
from core.agents import AgentCoordinator
from core.agents.specialists import AutomationAgent, ConversationAgent, MemoryAgent, PlanningAgent, ResearchWorkerAgent
from core.autonomy import GoalExecutor, TaskManager
from core.knowledge import KnowledgeBase
from core.monitoring import MetricsCollector
from core.reasoning import DecisionEngine, Planner
from core.research import ResearchAgent, WebSearchClient
from plugins.manager import PluginManager


class AutonomousNIRA:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger("nira.platform")
        self.metrics = MetricsCollector()
        self.knowledge_base = KnowledgeBase(settings.knowledge_path)
        self.plugin_manager = PluginManager()
        self.research_agent = ResearchAgent(WebSearchClient(max_results=settings.max_research_results))
        self.coordinator = AgentCoordinator(
            decision_engine=DecisionEngine(),
            conversation_agent=ConversationAgent(self.knowledge_base, self.plugin_manager),
            planning_agent=PlanningAgent(),
            research_agent=ResearchWorkerAgent(self.research_agent),
            automation_agent=AutomationAgent(),
            memory_agent=MemoryAgent(self.knowledge_base),
            metrics=self.metrics,
        )
        self.goal_executor = GoalExecutor(
            planner=Planner(max_steps=settings.max_plan_steps),
            coordinator=self.coordinator,
            task_manager=TaskManager(),
            metrics=self.metrics,
        )

    async def achieve_goal(self, goal: str):
        self.logger.info("goal.started", extra={"goal": goal})
        return await self.goal_executor.execute(goal)

    async def converse(self, message: str) -> str:
        result = await self.coordinator.converse(message)
        self.logger.info("conversation.completed", extra={"plugin": result.metadata.get("plugin")})
        return result.output

    def run_goal(self, goal: str):
        return self._run_sync(self.achieve_goal(goal))

    def chat(self, message: str) -> str:
        return self._run_sync(self.converse(message))

    @staticmethod
    def _run_sync(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
