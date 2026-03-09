from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class SafetyAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's safety agent. Prefer bounded, local, low-risk execution."
    role_name = "safety"
    task_type = "safety"

    def assess_risk(self, user_prompt: str, graph) -> str:
        lowered = user_prompt.lower()
        tokens = {token.strip(".,!?") for token in lowered.split()}
        if tokens & {"delete", "remove", "overwrite", "shutdown"}:
            return "high"
        if len(graph.nodes) >= 5 or any(node.tool == "run_build" for node in graph.nodes):
            return "medium"
        return "low"
