from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Agent execution result with route and context metadata."""

    text: str
    route: str
    model_alias: str
    context_tokens: int
    metadata: dict[str, object] = field(default_factory=dict)
