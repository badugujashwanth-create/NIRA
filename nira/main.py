from __future__ import annotations

from nira.config import ConfigLoader
from nira.core.agent_runtime import AgentRuntime
from nira.interface.interface_manager import InterfaceManager


NiraRuntime = AgentRuntime


def build_runtime() -> AgentRuntime:
    config = ConfigLoader().load()
    return AgentRuntime(config=config)


def main() -> int:
    runtime = build_runtime()
    interface = InterfaceManager(runtime)
    interface.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
