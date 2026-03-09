from __future__ import annotations


class WorkflowEngine:
    def __init__(self, pattern_detector, registry, workflow_memory) -> None:
        self.pattern_detector = pattern_detector
        self.registry = registry
        self.workflow_memory = workflow_memory

    def observe(self, trace: list[str], success: bool) -> str | None:
        if not success or not trace:
            return None
        matched, normalized = self.pattern_detector.observe(trace)
        if not matched:
            return None
        name = self.registry.suggest_name(trace)
        self.registry.register(name, trace, {"normalized": normalized})
        self.workflow_memory.record_trace(trace, success=True)
        return name
