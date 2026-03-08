"""Core execution pipeline and safety engines for Nira."""

from nira_agent.core.context_snapshot import ContextSnapshot, ContextSnapshotEngine
from nira_agent.core.edr_analysis import EDRAnalysis, EDRAnalyzer
from nira_agent.core.exceptions import (
    ExecutionTimeout,
    RiskViolation,
    SimulationError,
    ToolFailure,
    ValidationError,
)
from nira_agent.core.execution_controller import ExecutionController
from nira_agent.core.personality_middleware import PersonalityMiddleware
from nira_agent.core.risk_engine import RiskAssessment, RiskClassifier, classify_risk
from nira_agent.core.simulation import SimulationEngine, SimulationReport
from nira_agent.core.syscall_profile import CommandExecutionProfile, SyscallProfiler, SyscallProjection

__all__ = [
    "ContextSnapshot",
    "ContextSnapshotEngine",
    "EDRAnalysis",
    "EDRAnalyzer",
    "ExecutionController",
    "ExecutionTimeout",
    "PersonalityMiddleware",
    "RiskAssessment",
    "RiskClassifier",
    "RiskViolation",
    "SimulationEngine",
    "SimulationError",
    "SimulationReport",
    "SyscallProfiler",
    "SyscallProjection",
    "CommandExecutionProfile",
    "ToolFailure",
    "ValidationError",
    "classify_risk",
]
