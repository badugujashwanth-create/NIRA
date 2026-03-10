from core.reasoning import Planner


def test_planner_builds_research_steps() -> None:
    plan = Planner(max_steps=6).build_plan("Research the best laptops under $1500 and summarize.")
    capabilities = [step.capability for step in plan.steps]
    assert capabilities[0] == "conversation"
    assert "research" in capabilities
    assert "memory" in capabilities
    assert capabilities[-1] == "conversation"
