from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class CodingAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's coding agent. Focus on repository-aware implementation and local validation."
    role_name = "coding"
    task_type = "coding"
