from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class ResearchPlan:
    topic: str
    subtopics: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": self.topic,
            "subtopics": list(self.subtopics),
            "questions": list(self.questions),
        }


class TopicPlanner:
    def __init__(self, model) -> None:
        self.model = model

    def plan(self, request: str) -> ResearchPlan:
        cleaned = request.strip()
        topic = self._normalize_topic(cleaned)
        llm_plan = self._try_model_plan(topic)
        if llm_plan is not None:
            return llm_plan

        subtopics = self._heuristic_subtopics(topic)
        questions = [f"What is the role of {item} in {topic}?" for item in subtopics[:4]]
        return ResearchPlan(topic=topic, subtopics=subtopics, questions=questions)

    @staticmethod
    def _normalize_topic(request: str) -> str:
        normalized = re.sub(r"^(research|investigate|study|summarize|analyze)\s+", "", request, flags=re.IGNORECASE)
        normalized = normalized.strip().strip(".")
        normalized = normalized or request.strip() or "Research Topic"
        return normalized.title()

    def _try_model_plan(self, topic: str) -> ResearchPlan | None:
        if not self.model:
            return None
        prompt = (
            "Break this research request into a JSON object with keys "
            "`topic`, `subtopics`, and `questions`.\n"
            f"Request: {topic}\n"
            "Return JSON only."
        )
        try:
            response = self.model.generate(prompt).text.strip()
        except Exception:
            return None
        if not response:
            return None
        try:
            start = response.find("{")
            end = response.rfind("}")
            if start == -1 or end == -1:
                return None
            payload = json.loads(response[start : end + 1])
            subtopics = [str(item).strip() for item in payload.get("subtopics", []) if str(item).strip()]
            questions = [str(item).strip() for item in payload.get("questions", []) if str(item).strip()]
            topic_name = str(payload.get("topic", topic)).strip() or topic
            if not subtopics:
                return None
            return ResearchPlan(topic=topic_name, subtopics=subtopics[:8], questions=questions[:8])
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _heuristic_subtopics(topic: str) -> list[str]:
        keyword_map = {
            "authentication": ["Firebase Authentication", "OAuth2", "JWT Authentication", "Security Best Practices"],
            "android": ["Firebase Authentication", "OAuth2", "JWT Authentication", "Security Best Practices"],
            "database": ["Schema Design", "Query Performance", "Caching", "Backup Strategy"],
            "llama": ["Model Loading", "Prompt Design", "Inference Parameters", "Embedding Support"],
        }
        lowered = topic.lower()
        for key, subtopics in keyword_map.items():
            if key in lowered:
                return subtopics
        tokens = [token.title() for token in re.findall(r"[A-Za-z0-9]+", topic)[:3]]
        base = " ".join(tokens) or topic
        return [
            f"{base} Overview",
            f"{base} Core Concepts",
            f"{base} Implementation Patterns",
            f"{base} Best Practices",
        ]
