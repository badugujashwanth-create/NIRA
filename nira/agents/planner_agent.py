from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class PlannerAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's planning agent. Break goals into deterministic local execution steps."
    role_name = "planner"
    task_type = "planning"
