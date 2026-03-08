from __future__ import annotations

import re

from nira_agent.automation.models import ToolResult
from nira_agent.ai.structured_output import StructuredModelOutput


class ConfidenceScorer:
    _UNCERTAIN_PHRASES = (
        "i might be wrong",
        "not sure",
        "cannot verify",
        "uncertain",
        "i don't know",
    )

    def score(
        self,
        user_input: str,
        output: StructuredModelOutput,
        tool_results: list[ToolResult] | None = None,
    ) -> float:
        if not output.message and not output.tool_calls:
            return 0.0

        base = output.confidence if output.confidence > 0 else 0.55
        text = output.message.lower().strip()

        if not output.json_valid:
            base -= 0.35
        if not output.schema_valid:
            base -= 0.25
        if output.validation_errors:
            base -= min(0.25, len(output.validation_errors) * 0.06)

        if any(phrase in text for phrase in self._UNCERTAIN_PHRASES):
            base -= 0.25

        if re.search(r"\b(error|failed|unknown)\b", text):
            base -= 0.15

        if output.tool_calls:
            # Structured tool calls usually imply higher certainty for executable tasks.
            base += 0.10

        if tool_results:
            failures = sum(1 for r in tool_results if not r.ok)
            successes = sum(1 for r in tool_results if r.ok)
            if failures:
                base -= min(0.40, failures * 0.18)
            if successes and failures == 0:
                base += min(0.20, successes * 0.05)

        if len(user_input.strip()) < 3:
            base -= 0.2

        return max(0.0, min(1.0, base))
