from __future__ import annotations

from nira.agents.base import BaseRoleAgent


class EmotionAgent(BaseRoleAgent):
    system_prompt = "You are NIRA's emotion agent. Keep responses calm, direct, and concise."
    role_name = "emotion"
    task_type = "emotion"

    def polish_response(self, text: str, confidence: float) -> str:
        draft = text or "No response generated."
        context = {"confidence": confidence, "active_task": "final_response"}
        polished = self.respond(draft, context).text
        prefix = "High confidence: " if confidence >= 0.75 else "Status: "
        body = polished.strip()
        if len(body) < max(24, len(draft) // 4):
            body = draft
        return f"{prefix}{body.strip()}"
