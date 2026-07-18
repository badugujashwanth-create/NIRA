from __future__ import annotations

from pathlib import Path

from nira.config import NiraConfig
from nira.core.agent_runtime import AgentRuntime
from nira.memory.conversation_store import ConversationStore
from nira.models.llama_runtime import ModelResponse


class FakeModel:
    def generate(self, prompt: str) -> ModelResponse:
        return ModelResponse(text="remembered-response", provider="fake")

    def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]

    def close(self) -> None:
        return None


def test_conversation_lifecycle_search_and_export(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "runtime.db")
    conversation = store.create()
    store.add_message(conversation.conversation_id, "user", "Plan the lunar release checklist")
    store.add_message(conversation.conversation_id, "assistant", "Checklist ready")

    refreshed = store.get(conversation.conversation_id)
    assert refreshed is not None
    assert refreshed.title == "Plan the lunar release checklist"
    assert refreshed.message_count == 2
    assert store.search("lunar")[0]["conversation_id"] == conversation.conversation_id
    assert store.set_pinned(conversation.conversation_id, True)

    output = store.export_markdown(conversation.conversation_id, tmp_path / "exports" / "session.md")
    exported = output.read_text(encoding="utf-8")
    assert "# Plan the lunar release checklist" in exported
    assert "## User" in exported
    assert "Checklist ready" in exported
    assert store.delete(conversation.conversation_id)
    assert store.get(conversation.conversation_id) is None


def test_runtime_recovers_latest_session_and_recent_context(tmp_path: Path) -> None:
    config = NiraConfig(base_dir=tmp_path / "state")
    first = AgentRuntime(config=config, model=FakeModel())
    first.handle("Remember the blue deployment window")
    conversation_id = first.current_conversation.conversation_id
    title = first.current_conversation.title
    first.shutdown()

    recovered = AgentRuntime(config=NiraConfig(base_dir=tmp_path / "state"), model=FakeModel())
    assert recovered.current_conversation.conversation_id == conversation_id
    assert recovered.current_conversation.title == title
    turns = recovered.short_term_memory.snapshot()
    assert [turn.role for turn in turns[-2:]] == ["user", "assistant"]
    assert turns[-2].content == "Remember the blue deployment window"
    recovered.shutdown()


def test_switching_sessions_replaces_short_term_context(tmp_path: Path) -> None:
    runtime = AgentRuntime(config=NiraConfig(base_dir=tmp_path / "state"), model=FakeModel())
    first_id = runtime.current_conversation.conversation_id
    runtime.conversation_store.add_message(first_id, "user", "first context")
    second = runtime.new_conversation("Second")
    runtime.conversation_store.add_message(second.conversation_id, "user", "second context")

    runtime.switch_conversation(first_id)
    assert [turn.content for turn in runtime.short_term_memory.snapshot()] == ["first context"]
    runtime.switch_conversation(second.conversation_id)
    assert [turn.content for turn in runtime.short_term_memory.snapshot()] == ["second context"]
    runtime.shutdown()


def test_latest_session_is_not_overridden_by_an_older_pin(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "runtime.db")
    pinned = store.create("Pinned reference")
    assert store.set_pinned(pinned.conversation_id, True)
    latest = store.create("Latest work")

    assert store.latest_or_create().conversation_id == latest.conversation_id
