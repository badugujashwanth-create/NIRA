from __future__ import annotations


class ConfidenceEngine:
    def score(self, state, execution) -> float:
        plan_size = max(1, len(state.plan))
        successes = sum(1 for result in execution.results if result.ok)
        memory_bonus = min(0.2, 0.05 * sum(bool(value) for value in state.memory_hits.values()))
        risk_penalty = {"low": 0.0, "medium": 0.08, "high": 0.18}.get(state.risk_level, 0.12)
        score = (successes / plan_size) + memory_bonus - risk_penalty
        return round(max(0.0, min(1.0, score)), 2)
