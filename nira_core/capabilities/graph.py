from __future__ import annotations

from dataclasses import dataclass, field

from nira_core.capabilities.registry import Capability, CapabilityRegistry


@dataclass(frozen=True, slots=True)
class WorkflowPlan:
    """Ordered capability plan for an adaptive workflow."""

    goal: str
    capabilities: list[Capability]
    estimated_latency_ms: int
    estimated_ram_mb: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "goal": self.goal,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
            "estimated_latency_ms": self.estimated_latency_ms,
            "estimated_ram_mb": self.estimated_ram_mb,
            "notes": list(self.notes),
        }


class CapabilityGraph:
    """Dependency graph traversal and workflow composition."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def resolve_dependencies(self, capability_name: str) -> list[Capability]:
        """Return dependencies before the requested capability."""

        visited: set[str] = set()
        ordered: list[Capability] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            capability = self._registry.get(name)
            for dependency in capability.dependencies:
                visit(dependency)
            ordered.append(capability)

        visit(capability_name)
        return ordered

    def compose(self, goal: str, recommended: list[Capability], ram_limit_mb: int) -> WorkflowPlan:
        """Compose a workflow, pruning optional steps when RAM estimates exceed budget."""

        ordered: list[Capability] = []
        notes: list[str] = []
        seen: set[str] = set()
        for capability in recommended:
            for item in self.resolve_dependencies(capability.name):
                if item.name not in seen:
                    ordered.append(item)
                    seen.add(item.name)
        total_ram = sum(item.ram_mb for item in ordered)
        if total_ram > ram_limit_mb:
            notes.append("Pruned highest-RAM optional capabilities to stay within budget.")
            ordered = sorted(ordered, key=lambda item: item.ram_mb)
            while sum(item.ram_mb for item in ordered) > ram_limit_mb and len(ordered) > 1:
                ordered.pop()
        return WorkflowPlan(
            goal=goal,
            capabilities=ordered,
            estimated_latency_ms=sum(item.latency_ms for item in ordered),
            estimated_ram_mb=sum(item.ram_mb for item in ordered),
            notes=notes,
        )
