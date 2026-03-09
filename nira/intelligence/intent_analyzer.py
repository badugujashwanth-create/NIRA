from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class IntentResult:
    kind: str
    goal: str
    agent_role: str
    needs_web: bool = False
    risk_level: str = "low"
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "goal": self.goal,
            "agent_role": self.agent_role,
            "needs_web": self.needs_web,
            "risk_level": self.risk_level,
            "keywords": list(self.keywords),
        }


class IntentAnalyzer:
    def analyze(self, user_input: str) -> IntentResult:
        text = user_input.strip()
        lowered = text.lower()
        keywords = [token for token in re.findall(r"[a-z0-9_]{3,}", lowered)[:12]]
        if any(word in lowered for word in {"research", "investigate", "compare", "survey"}) or lowered.startswith(
            "find "
        ):
            return IntentResult(
                kind="research_topic",
                goal=text,
                agent_role="research_agent",
                needs_web=any(word in lowered for word in {"web", "internet", "online", "latest"}),
                risk_level="low",
                keywords=keywords,
            )
        if any(word in lowered for word in {"document", "report", "markdown", "pdf", "txt", "write docs"}):
            return IntentResult("document", text, "document_agent", keywords=keywords)
        if any(
            word in lowered
            for word in {
                "code",
                "build",
                "test",
                "refactor",
                "implement",
                "fix",
                "bug",
                "feature",
                "integrate",
                "repo",
                "repository",
                "authentication",
            }
        ):
            return IntentResult("coding", text, "coding_agent", risk_level=self._risk_level(lowered), keywords=keywords)
        if any(word in lowered for word in {"workflow", "routine", "automation", "repeat"}):
            return IntentResult("workflow", text, "planner_agent", risk_level="medium", keywords=keywords)
        return IntentResult("chat", text, "planner_agent", risk_level=self._risk_level(lowered), keywords=keywords)

    @staticmethod
    def _risk_level(text: str) -> str:
        if any(word in text for word in {"delete", "remove", "drop", "kill", "wipe"}):
            return "high"
        if any(word in text for word in {"update", "modify", "install", "run"}):
            return "medium"
        return "low"
