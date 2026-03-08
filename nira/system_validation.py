from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


@dataclass
class CheckResult:
    component: str
    ok: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": "ok" if self.ok else "error",
            "details": self.details,
        }


@dataclass
class HealthReport:
    ok: bool
    generated_at: str
    checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "generated_at": self.generated_at,
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_text(self) -> str:
        return self.to_json()


def run_system_health_checks(runtime) -> HealthReport:
    checks: list[CheckResult] = []
    controller = getattr(runtime, "controller", None)

    # LLM connectivity
    llm_url = runtime.cfg.local_llm_base_url.rstrip("/")
    llm_ok = False
    llm_detail = ""
    for endpoint in ("/health", "/v1/models"):
        try:
            res = requests.get(llm_url + endpoint, timeout=(3, 5))
            if res.status_code == 200:
                llm_ok = True
                llm_detail = f"{endpoint} responded 200"
                break
            llm_detail = f"{endpoint} responded {res.status_code}"
        except Exception as exc:
            llm_detail = str(exc)
    checks.append(CheckResult("llm_connectivity", llm_ok, llm_detail))

    # SQL database state
    sql_ok = bool(runtime.sql_store.available)
    checks.append(
        CheckResult(
            "sql_database",
            sql_ok,
            "SQL connected with pooling" if sql_ok else "SQL unavailable; fallback storage active",
        )
    )

    # Tool registry integrity
    reg = runtime.automation.registry_validation_report()
    checks.append(CheckResult("tool_registry_integrity", reg.ok, reg.output))

    # Risk engine
    risk_ok = controller is not None and getattr(controller, "risk_classifier", None) is not None
    checks.append(CheckResult("risk_engine", risk_ok, "initialized" if risk_ok else "not initialized"))

    # Simulation engine
    simulation_ok = controller is not None and getattr(controller, "simulation_engine", None) is not None
    checks.append(
        CheckResult("simulation_engine", simulation_ok, "initialized" if simulation_ok else "not initialized")
    )

    # EDR analysis module
    edr_ok = controller is not None and getattr(controller, "edr_analyzer", None) is not None
    checks.append(CheckResult("edr_analysis_module", edr_ok, "initialized" if edr_ok else "not initialized"))

    # Syscall profiling module
    syscall_ok = controller is not None and getattr(controller, "syscall_profiler", None) is not None
    checks.append(
        CheckResult("syscall_profiling_module", syscall_ok, "initialized" if syscall_ok else "not initialized")
    )

    # Personality middleware
    personality_ok = controller is not None and getattr(controller, "personality_middleware", None) is not None
    checks.append(
        CheckResult(
            "personality_middleware",
            personality_ok,
            "initialized" if personality_ok else "not initialized",
        )
    )

    # Optional workflow file integrity check
    workflow_path = getattr(runtime, "workflow_path", Path.cwd() / runtime.cfg.dsl_workflow_file)
    workflow = validate_workflow_file(workflow_path, runtime.automation.dsl_parser, runtime.automation.registry)
    checks.append(workflow)

    return HealthReport(
        ok=all(c.ok for c in checks),
        generated_at=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )


def validate_workflow_file(path: Path, parser, registry) -> CheckResult:
    if not path.exists():
        return CheckResult("workflow_dsl", False, f"Workflow file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult("workflow_dsl", False, f"Read error: {exc}")
    parsed = parser.parse(text)
    if parsed.errors:
        return CheckResult("workflow_dsl", False, "; ".join(parsed.errors))

    issues: list[str] = []
    for wf in parsed.workflows.values():
        for step in wf.steps:
            v = registry.validate_call(step)
            if not v.ok:
                issues.append(f"{wf.name}:{step.tool} -> {v.output}")
    if issues:
        return CheckResult("workflow_dsl", False, "; ".join(issues))
    return CheckResult("workflow_dsl", True, f"{len(parsed.workflows)} workflows validated")


def validate_tool_registry(registry) -> CheckResult:
    issues = registry.validate_registry()
    if issues:
        return CheckResult("tool_registry_integrity", False, "; ".join(issues))
    return CheckResult("tool_registry_integrity", True, f"{len(registry.list_tools())} tools validated")
