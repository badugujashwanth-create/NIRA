from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class DocumentAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's document agent. Produce concise, structured markdown-ready content."
    role_name = "document"
    task_type = "document"
