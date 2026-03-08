from __future__ import annotations

from dataclasses import dataclass

from nira_agent.automation.models import ToolCall


@dataclass(frozen=True)
class EDRAnalysis:
    process_creation: bool
    file_writes: bool
    registry_modifications: bool
    thread_creation: bool
    memory_protection_changes: bool
    detection_likelihood: str
    summary: str


class EDRAnalyzer:
    """Analytical telemetry prediction engine (no bypass behavior)."""

    def analyze(self, call: ToolCall) -> EDRAnalysis:
        tool = call.tool.lower().strip()
        process_creation = tool in {"open_app", "close_app"}
        file_writes = tool in {"write_file", "move_file", "delete_file", "create_folder", "take_screenshot"}
        registry_modifications = "registry" in tool
        thread_creation = process_creation
        memory_protection_changes = tool in {"open_app"}

        risk_score = 0
        risk_score += 2 if process_creation else 0
        risk_score += 2 if file_writes else 0
        risk_score += 3 if registry_modifications else 0
        risk_score += 2 if memory_protection_changes else 0

        if risk_score >= 6:
            likelihood = "high"
        elif risk_score >= 3:
            likelihood = "medium"
        else:
            likelihood = "low"

        summary = (
            f"TelemetryPrediction(tool={call.tool}, process_creation={process_creation}, "
            f"file_writes={file_writes}, registry_modifications={registry_modifications}, "
            f"thread_creation={thread_creation}, memory_protection_changes={memory_protection_changes}, "
            f"detection_likelihood={likelihood})"
        )
        return EDRAnalysis(
            process_creation=process_creation,
            file_writes=file_writes,
            registry_modifications=registry_modifications,
            thread_creation=thread_creation,
            memory_protection_changes=memory_protection_changes,
            detection_likelihood=likelihood,
            summary=summary,
        )
