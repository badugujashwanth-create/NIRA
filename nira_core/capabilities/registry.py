from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Capability:
    """Metadata used to compose local workflows under resource limits."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 1000
    ram_mb: int = 50
    required_permissions: tuple[str, ...] = ()
    compatible_models: tuple[str, ...] = ()
    execution_type: str = "async"
    dependencies: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityRegistry:
    """Dynamic registry for tools, models, and orchestration skills."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        try:
            return self._capabilities[name]
        except KeyError as exc:
            raise KeyError(f"Unknown capability: {name}") from exc

    def list(self) -> list[Capability]:
        return sorted(self._capabilities.values(), key=lambda capability: capability.name)

    def find_by_tag(self, tag: str) -> list[Capability]:
        return [capability for capability in self.list() if tag in capability.tags]

    def discover_tools(self, tool_names: list[str]) -> None:
        """Register basic metadata for currently available tool facades."""

        defaults = {
            "browser": Capability(
                name="browser.extract",
                description="Navigate websites and extract visible content with Playwright.",
                latency_ms=3000,
                ram_mb=200,
                required_permissions=("network",),
                execution_type="async",
                tags=("browser", "io", "network"),
            ),
            "filesystem": Capability(
                name="filesystem.readwrite",
                description="Read, write, and list files inside the configured workspace.",
                latency_ms=50,
                ram_mb=10,
                required_permissions=("filesystem",),
                execution_type="async",
                tags=("filesystem", "tool"),
            ),
            "shell": Capability(
                name="shell.allowlisted",
                description="Run allowlisted commands in the restricted subprocess sandbox.",
                latency_ms=1000,
                ram_mb=80,
                required_permissions=("subprocess",),
                execution_type="async",
                tags=("shell", "tool"),
            ),
            "retrieval": Capability(
                name="retrieval.semantic",
                description="Search semantic and episodic memory with BGE reranking.",
                latency_ms=250,
                ram_mb=150,
                compatible_models=("fast",),
                execution_type="async",
                tags=("retrieval", "memory"),
            ),
            "local_api": Capability(
                name="local_api.call",
                description="Call explicitly local HTTP APIs.",
                latency_ms=200,
                ram_mb=30,
                required_permissions=("local_network",),
                execution_type="async",
                tags=("api", "tool"),
            ),
        }
        for tool_name in tool_names:
            capability = defaults.get(tool_name)
            if capability is not None:
                self.register(capability)
