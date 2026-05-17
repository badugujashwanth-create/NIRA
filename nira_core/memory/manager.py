from __future__ import annotations

from pathlib import Path
from dataclasses import asdict

from nira_core.config import NiraConfig
from nira_core.events import Event, EventBus, EventType
from nira_core.memory.episodic import EpisodicMemory
from nira_core.memory.semantic import SemanticDocument, SemanticMemory
from nira_core.memory.working import WorkingMemory
from nira_core.retrieval.embedding import EmbeddingProvider
from nira_core.telemetry import Telemetry


class MemoryManager:
    """Coordinates working, episodic, and semantic memory tiers."""

    def __init__(
        self,
        config: NiraConfig,
        telemetry: Telemetry,
        embedding_provider: EmbeddingProvider | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config = config
        self._telemetry = telemetry
        self._event_bus = event_bus
        self.working = WorkingMemory(config.memory.working_max_items, config.memory.working_ttl_sec)
        self.episodic = EpisodicMemory(Path(config.data_dir) / "episodic.sqlite3", config.memory)
        self.semantic = SemanticMemory(
            Path(config.data_dir) / "chroma",
            embedding_provider or EmbeddingProvider(),
        )

    def remember_task(self, task: str, result: str, importance: float = 0.5) -> None:
        """Store completed task traces in bounded long-term memory."""

        content = f"Task: {task}\nResult: {result}"
        episode_id = self.episodic.append("task", content, importance=importance)
        self.semantic.add(f"task:{episode_id}", content, {"kind": "task"})
        self._telemetry.increment("memory_writes_total")
        self._telemetry.emit("memory.write", {"kind": "task", "importance": importance})
        if self._event_bus is not None:
            self._event_bus.publish_nowait(
                Event.create(EventType.MEMORY_UPDATED, {"kind": "task", "episode_id": episode_id, "importance": importance})
            )

    def search(self, query: str, limit: int | None = None) -> list[SemanticDocument]:
        """Search semantic memory and emit latency telemetry."""

        import time

        started = time.perf_counter()
        items = self.semantic.search(query, limit or self._config.memory.semantic_top_k)
        self._telemetry.observe("retrieval_latency_seconds", time.perf_counter() - started)
        self._telemetry.gauge("retrieval_result_count", len(items))
        useful = sum(1 for item in items if item.score >= 0.35)
        irrelevant = max(0, len(items) - useful)
        useful_percent = (useful / len(items)) if items else 0.0
        self._telemetry.gauge("memory_useful_recall_percent", useful_percent)
        self._telemetry.gauge("memory_irrelevant_recall_count", irrelevant)
        self._telemetry.emit(
            "memory.recall_quality",
            {"results": len(items), "useful_percent": round(useful_percent, 3), "irrelevant": irrelevant},
        )
        return items

    def timeline(self, limit: int = 50, include_archived: bool = False) -> list[dict[str, object]]:
        """Return durable memories for UI inspection."""

        return [asdict(episode) for episode in self.episodic.timeline(limit, include_archived)]

    def recent_context(self, limit: int = 8) -> str:
        """Return compact recent context for workflows."""

        episodes = self.episodic.recent(limit)
        return "\n\n".join(episode.content for episode in episodes)

    def summaries(self, limit: int = 20) -> list[dict[str, object]]:
        """Return compact memory summaries."""

        return self.episodic.summaries(limit)

    def delete(self, episode_id: int) -> bool:
        """Delete one memory entry."""

        ok = self.episodic.delete(episode_id)
        if ok:
            self._telemetry.emit("memory.delete", {"episode_id": episode_id})
        return ok

    def pin(self, episode_id: int, pinned: bool = True) -> bool:
        """Pin or unpin one memory entry."""

        ok = self.episodic.pin(episode_id, pinned)
        if ok:
            self._telemetry.emit("memory.pin", {"episode_id": episode_id, "pinned": pinned})
        return ok

    def archive(self, episode_id: int) -> bool:
        """Archive one memory entry."""

        ok = self.episodic.archive(episode_id)
        if ok:
            self._telemetry.emit("memory.archive", {"episode_id": episode_id})
        return ok

    def maintain(self) -> dict[str, int]:
        """Run decay and pruning maintenance."""

        self.working.prune()
        result = self.episodic.decay_and_prune()
        health = self.health()
        self._telemetry.gauge("memory_active_items", float(health["active"]))
        self._telemetry.gauge("memory_fragmentation", float(health["fragmentation"]))
        self._telemetry.emit("memory.maintenance", {**result, "health": health})
        return result

    def health(self) -> dict[str, object]:
        """Return memory health metrics for validation and UI."""

        return self.episodic.health()
