from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from nira_agent.automation.models import ToolCall
from nira_agent.core.edr_analysis import EDRAnalysis
from nira_agent.core.exceptions import SimulationError
from nira_agent.core.risk_engine import RiskAssessment
from nira_agent.core.syscall_profile import SyscallProjection
from nira_agent.storage.sql_store import SQLStore


@dataclass(frozen=True)
class SimulationReport:
    impacted_files: list[str] = field(default_factory=list)
    process_changes: list[str] = field(default_factory=list)
    system_impact: str = "low"
    syscall_intensity: str = "low"
    detection_telemetry_signals: list[str] = field(default_factory=list)
    summary: str = ""


class SimulationEngine:
    """Predictive engine. Never performs the real operation."""

    def simulate(
        self,
        call: ToolCall,
        risk: RiskAssessment,
        edr: EDRAnalysis,
        syscall_projection: SyscallProjection,
    ) -> SimulationReport:
        try:
            files = self._predict_files(call)
            proc = self._predict_process_changes(call)
            telemetry = self._predict_telemetry(edr)
            impact = risk.level if risk.level in {"low", "medium", "high", "critical"} else "medium"
            summary = (
                f"Simulation(tool={call.tool}, impact={impact}, syscall_intensity={syscall_projection.syscall_intensity}, "
                f"files={len(files)}, process_changes={len(proc)}, telemetry={edr.detection_likelihood})"
            )
            return SimulationReport(
                impacted_files=files,
                process_changes=proc,
                system_impact=impact,
                syscall_intensity=syscall_projection.syscall_intensity,
                detection_telemetry_signals=telemetry,
                summary=summary,
            )
        except Exception as exc:
            raise SimulationError(f"Simulation failed for tool '{call.tool}': {exc}") from exc

    @staticmethod
    def persist(sql_store: SQLStore | None, call: ToolCall, risk: RiskAssessment, report: SimulationReport) -> None:
        if sql_store is None:
            return
        sql_store.insert_simulation(
            ts=datetime.now(timezone.utc).isoformat(),
            command_name=call.tool,
            risk_level=risk.level,
            impacted_files=report.impacted_files,
            process_changes=report.process_changes,
            system_impact=report.system_impact,
            syscall_intensity=report.syscall_intensity,
            telemetry_signals=report.detection_telemetry_signals,
            summary=report.summary,
        )

    @staticmethod
    def _predict_files(call: ToolCall) -> list[str]:
        touched: list[str] = []
        for key in ("path", "src", "dst"):
            value = call.args.get(key)
            if isinstance(value, str) and value.strip():
                touched.append(str(Path(value.strip()).expanduser()))
        return touched

    @staticmethod
    def _predict_process_changes(call: ToolCall) -> list[str]:
        tool = call.tool.lower().strip()
        if tool == "open_app":
            return ["new_process_start"]
        if tool == "close_app":
            return ["process_termination"]
        return []

    @staticmethod
    def _predict_telemetry(edr: EDRAnalysis) -> list[str]:
        signals: list[str] = []
        if edr.process_creation:
            signals.append("process_creation")
        if edr.file_writes:
            signals.append("file_write")
        if edr.registry_modifications:
            signals.append("registry_write")
        if edr.thread_creation:
            signals.append("thread_create")
        if edr.memory_protection_changes:
            signals.append("memory_protect")
        return signals
