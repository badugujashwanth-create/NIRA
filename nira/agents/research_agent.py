from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class ResearchAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's research agent. Prefer local evidence and use the web only when allowed."
    role_name = "research"
    task_type = "research"
