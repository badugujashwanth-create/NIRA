from __future__ import annotations

from nira_agent.ai.structured_output import StructuredModelOutput, StructuredOutputParser


class RoutingResponseParser:
    def __init__(self) -> None:
        self._parser = StructuredOutputParser()

    def parse(self, raw_text: str) -> StructuredModelOutput:
        return self._parser.parse(raw_text)

