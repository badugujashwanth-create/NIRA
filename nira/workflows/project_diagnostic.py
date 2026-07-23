from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Event
from typing import Any, Callable

from nira.tools import ToolRegistry, ToolResult


@dataclass(frozen=True)
class DiagnosticEvent:
    stage: str
    status: str
    message: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class ProjectDiagnosticReport:
    ok: bool
    workspace: str
    query: str
    plan: list[dict[str, str]]
    timeline: list[DiagnosticEvent]
    inspection: dict[str, Any] = field(default_factory=dict)
    search: dict[str, Any] = field(default_factory=dict)
    diagnostic: dict[str, Any] = field(default_factory=dict)
    verification: dict[str, Any] = field(default_factory=dict)
    permission: dict[str, Any] = field(default_factory=dict)
    recoverable: bool = False
    cancelled: bool = False
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "workspace": self.workspace,
            "query": self.query,
            "plan": list(self.plan),
            "timeline": [item.to_dict() for item in self.timeline],
            "inspection": dict(self.inspection),
            "search": dict(self.search),
            "diagnostic": dict(self.diagnostic),
            "verification": dict(self.verification),
            "permission": dict(self.permission),
            "recoverable": self.recoverable,
            "cancelled": self.cancelled,
            "session_id": self.session_id,
        }


ProgressCallback = Callable[[DiagnosticEvent], None]


class ProjectDiagnosticWorkflow:
    """One bounded project-understanding and verification workflow."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def run(
        self,
        *,
        workspace: str,
        query: str,
        profile: str,
        state: Any,
        cancel_event: Event,
        progress_callback: ProgressCallback | None = None,
    ) -> ProjectDiagnosticReport:
        plan = [
            {"stage": "inspect", "label": "Inspect project structure safely"},
            {"stage": "search", "label": f"Search bounded text evidence for {query!r}"},
            {"stage": "permission", "label": "Request one-time process approval"},
            {"stage": "diagnostic", "label": f"Run allowlisted {profile} diagnostic"},
            {"stage": "verify", "label": "Verify exit code and captured evidence"},
            {"stage": "memory", "label": "Preserve the result in the local session"},
        ]
        report = ProjectDiagnosticReport(
            ok=False,
            workspace=workspace,
            query=query,
            plan=plan,
            timeline=[],
        )

        if self._cancelled(report, cancel_event, progress_callback):
            return report
        inspection = self.registry.execute("analyze_project", {"path": "."}, state)
        report.inspection = inspection.to_dict()
        self._record(report, "inspect", inspection, progress_callback)
        if not inspection.ok:
            report.recoverable = True
            return report

        if self._cancelled(report, cancel_event, progress_callback):
            return report
        search = self.registry.execute(
            "search_workspace",
            {"path": ".", "query": query, "max_files": 500, "max_matches": 50},
            state,
        )
        report.search = search.to_dict()
        self._record(report, "search", search, progress_callback)
        if not search.ok:
            report.recoverable = True
            return report

        if self._cancelled(report, cancel_event, progress_callback):
            return report
        request = {
            "profile": profile,
            "cwd": ".",
            "requested_action": f"Run the allowlisted {profile} diagnostic",
            "reason": "Verify the selected project with local execution evidence",
            "target": workspace,
            "expected_effect": "Read source files and create interpreter cache files only",
            "risk": "Executes a fixed local Python module; arbitrary commands are rejected",
        }
        diagnostic = self.registry.execute("run_build", request, state)
        report.diagnostic = diagnostic.to_dict()
        decisions = self.registry.permission_policy.recent_decisions(limit=1)
        report.permission = decisions[-1] if decisions else {}
        self._record(report, "diagnostic", diagnostic, progress_callback)
        if not diagnostic.ok:
            report.recoverable = True
            return report

        verified = bool(
            diagnostic.data.get("verified")
            and diagnostic.data.get("returncode") == 0
            and diagnostic.data.get("profile") == profile
        )
        report.verification = {
            "verified": verified,
            "profile": diagnostic.data.get("profile"),
            "returncode": diagnostic.data.get("returncode"),
            "captured_output": bool(diagnostic.output.strip()),
            "search_match_count": search.data.get("match_count", 0),
        }
        verification = ToolResult(
            verified,
            "Diagnostic evidence verified." if verified else "Diagnostic evidence could not be verified.",
            report.verification,
        )
        self._record(report, "verify", verification, progress_callback)
        report.ok = verified
        report.recoverable = not verified
        return report

    @staticmethod
    def _record(
        report: ProjectDiagnosticReport,
        stage: str,
        result: ToolResult,
        callback: ProgressCallback | None,
    ) -> None:
        event = DiagnosticEvent(
            stage=stage,
            status="completed" if result.ok else "failed",
            message=result.output.splitlines()[0][:240] if result.output else stage,
        )
        report.timeline.append(event)
        if callback is not None:
            callback(event)

    @staticmethod
    def _cancelled(
        report: ProjectDiagnosticReport,
        cancel_event: Event,
        callback: ProgressCallback | None,
    ) -> bool:
        if not cancel_event.is_set():
            return False
        event = DiagnosticEvent(
            stage="cancelled",
            status="cancelled",
            message="The diagnostic stopped before the next tool started.",
        )
        report.timeline.append(event)
        report.cancelled = True
        report.recoverable = True
        if callback is not None:
            callback(event)
        return True
