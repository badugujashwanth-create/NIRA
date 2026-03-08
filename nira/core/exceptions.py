from __future__ import annotations

from typing import Any


class BackendError(Exception):
    """Base exception for controlled backend failures."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class ToolFailure(BackendError):
    """Tool execution failed in a non-recoverable way."""


class RiskViolation(BackendError):
    """Operation violated risk policy."""


class ValidationError(BackendError):
    """Input, schema, whitelist, or path validation failed."""


class ExecutionTimeout(BackendError):
    """Execution timed out."""


class SimulationError(BackendError):
    """Simulation pipeline failed."""
