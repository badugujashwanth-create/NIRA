from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RepairDecision:
    attempted: bool
    args: dict[str, object]
    reason: str


class RepairLoop:
    def __init__(self, reflection_engine, max_attempts: int = 1) -> None:
        self.reflection_engine = reflection_engine
        self.max_attempts = max_attempts

    def decide(self, node, args: dict[str, object], result) -> RepairDecision:
        if self.max_attempts <= 0:
            return RepairDecision(False, dict(args), "repair disabled")
        new_args = self.reflection_engine.suggest_repair(node.tool, args, result.output)
        if new_args == args:
            return RepairDecision(False, dict(args), "no repair delta")
        return RepairDecision(True, new_args, "reflection suggested updated args")
