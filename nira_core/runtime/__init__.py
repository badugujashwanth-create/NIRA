"""Production-like startup, shutdown, and demo runtime helpers."""

from nira_core.runtime.demo import print_demo, run_demo
from nira_core.runtime.startup import RuntimeStartupManager, StartupCheck, StartupReport

__all__ = ["RuntimeStartupManager", "StartupCheck", "StartupReport", "print_demo", "run_demo"]
