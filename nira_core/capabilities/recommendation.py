from __future__ import annotations

from nira_core.capabilities.graph import CapabilityGraph, WorkflowPlan
from nira_core.capabilities.registry import Capability, CapabilityRegistry


class CapabilityRecommendationEngine:
    """Goal-to-capability recommendation using lightweight heuristics."""

    def __init__(self, registry: CapabilityRegistry, graph: CapabilityGraph) -> None:
        self._registry = registry
        self._graph = graph

    def recommend(self, goal: str, max_ram_mb: int = 512, permissions: set[str] | None = None) -> WorkflowPlan:
        text = goal.lower()
        permissions = permissions or set()
        candidates: list[Capability] = []
        if any(term in text for term in ("search", "website", "browser", "page", "form")):
            candidates.extend(self._registry.find_by_tag("browser"))
        if any(term in text for term in ("memory", "remember", "context", "retrieve", "similar")):
            candidates.extend(self._registry.find_by_tag("retrieval"))
        if any(term in text for term in ("file", "read", "write", "project")):
            candidates.extend(self._registry.find_by_tag("filesystem"))
        if any(term in text for term in ("test", "command", "run", "build")):
            candidates.extend(self._registry.find_by_tag("shell"))
        if not candidates:
            candidates.extend(self._registry.find_by_tag("retrieval"))
        allowed = [
            capability
            for capability in _dedupe(candidates)
            if not capability.required_permissions or set(capability.required_permissions).issubset(permissions)
        ]
        if not allowed:
            allowed = _dedupe(candidates)
        return self._graph.compose(goal, allowed, ram_limit_mb=max_ram_mb)


def _dedupe(capabilities: list[Capability]) -> list[Capability]:
    seen: set[str] = set()
    output: list[Capability] = []
    for capability in capabilities:
        if capability.name in seen:
            continue
        seen.add(capability.name)
        output.append(capability)
    return output
