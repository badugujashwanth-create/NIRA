"""Structured logging and Prometheus-compatible metrics."""

from nira_core.telemetry.metrics import Telemetry
from nira_core.telemetry.resources import sample_resources

__all__ = ["Telemetry", "sample_resources"]
