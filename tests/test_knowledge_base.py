from core.knowledge import KnowledgeBase


def test_knowledge_base_returns_relevant_match(workspace_tmp_path) -> None:
    base = KnowledgeBase(workspace_tmp_path / "knowledge.json")
    base.add(topic="laptops", content="Laptop A costs 1400 dollars and has 16GB RAM.", source="source-a")
    base.add(topic="gardening", content="Tomatoes grow well in warm soil.", source="source-b")

    matches = base.search("best laptop under 1500", limit=1)

    assert matches
    assert matches[0].topic == "laptops"
