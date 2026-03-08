from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PersonalityMode:
    name: str
    tone: str
    style_rules: str


class PersonalityEngine:
    MODES = {
        "focus": PersonalityMode(
            name="Focus",
            tone="concise",
            style_rules="Prioritize action-first responses and short bullet points.",
        ),
        "calm": PersonalityMode(
            name="Calm",
            tone="supportive",
            style_rules="Use steady pacing and low-pressure wording.",
        ),
        "strategy": PersonalityMode(
            name="Strategy",
            tone="analytical",
            style_rules="Surface tradeoffs, risks, and next-best alternatives.",
        ),
        "night": PersonalityMode(
            name="Night",
            tone="gentle",
            style_rules="Keep outputs brief and low-stimulation with minimal chatter.",
        ),
    }

    def __init__(self, initial_mode: str = "focus") -> None:
        self._mode_key = initial_mode.lower() if initial_mode.lower() in self.MODES else "focus"

    def set_mode(self, mode: str) -> PersonalityMode:
        key = mode.strip().lower()
        if key in self.MODES:
            self._mode_key = key
        return self.current()

    def current(self) -> PersonalityMode:
        return self.MODES[self._mode_key]

    def build_system_prompt(self) -> str:
        mode = self.current()
        return (
            "You are Nira. Respond in strict JSON only.\n"
            "Keys: message, tool_calls, confidence, goal_achieved(optional).\n"
            "tool_calls format: [{\"tool\": string, \"args\": object}] and max one item.\n"
            f"mode={mode.name}; tone={mode.tone}\n"
        )
