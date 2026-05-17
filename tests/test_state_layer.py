from __future__ import annotations

from nira_core.state import reset_system_state


def test_system_state_tracks_runtime_signals() -> None:
    state = reset_system_state()
    state.set_active_model("primary_coding")
    state.set_resources(8421, 71)
    state.set_queue_depth("inference", 3)
    state.start_task("task-1", "coding", {"goal": "test"})
    state.record_compression(0.38)
    state.record_hallucination_score(0.12)
    state.record_retrieval_precision(0.81)

    snapshot = state.snapshot()
    assert snapshot["active_model"] == "primary_coding"
    assert snapshot["resident_models"] == ["primary_coding"]
    assert snapshot["ram_usage_mb"] == 8421
    assert snapshot["queue_depth"]["inference"] == 3
    assert snapshot["active_tasks"][0]["id"] == "task-1"
    assert snapshot["compression_ratio"] == 0.38
    assert snapshot["hallucination_score"] == 0.12
    assert snapshot["retrieval_precision"] == 0.81

    state.finish_task("task-1")
    assert state.snapshot()["active_tasks"] == []
