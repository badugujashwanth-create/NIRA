from __future__ import annotations

from pathlib import Path

# Compatibility package: map historical `nira_agent.*` imports to the `nira/` source tree.
_SOURCE_ROOT = Path(__file__).resolve().parent.parent / "nira"
__path__ = [str(_SOURCE_ROOT)]
