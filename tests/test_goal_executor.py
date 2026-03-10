from config.settings import Settings
from core import AutonomousNIRA
from core.research import ResearchFinding, ResearchSummary


async def _fake_research(query: str) -> ResearchSummary:
    return ResearchSummary(
        query=query,
        findings=[
            ResearchFinding("Laptop A", "https://example.com/a", "Laptop A offers strong battery life at 1400 dollars."),
            ResearchFinding("Laptop B", "https://example.com/b", "Laptop B offers a fast processor at 1499 dollars."),
        ],
        summary="Laptop A and Laptop B are strong options under 1500 dollars.",
        metadata={"sources": 2},
    )


def test_goal_executor_runs_research_goal(workspace_tmp_path) -> None:
    settings = Settings(
        project_root=workspace_tmp_path,
        data_dir=workspace_tmp_path / "data",
        cache_dir=workspace_tmp_path / "cache",
        knowledge_path=workspace_tmp_path / "data" / "knowledge.json",
    )
    platform = AutonomousNIRA(settings)
    platform.coordinator.agents["research"].research_agent.research = _fake_research

    result = platform.run_goal("Research the best laptops under $1500 and summarize.")

    assert "Laptop A" in result.summary
    assert all(task.status == "completed" for task in result.tasks)
    assert platform.knowledge_base.all()


def test_goal_executor_disables_plugins_during_goal_flow(workspace_tmp_path) -> None:
    settings = Settings(
        project_root=workspace_tmp_path,
        data_dir=workspace_tmp_path / "data",
        cache_dir=workspace_tmp_path / "cache",
        knowledge_path=workspace_tmp_path / "data" / "knowledge.json",
    )
    platform = AutonomousNIRA(settings)

    result = platform.run_goal("schedule calendar review for tomorrow")

    assert result.tasks[0].status == "completed"
    assert "Calendar plugin received" not in result.tasks[0].result
