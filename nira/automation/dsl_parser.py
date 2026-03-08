from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class DSLParseResult:
    modes: dict[str, list[str]]
    errors: list[str]


class DSLParser:
    _MODE_RE = re.compile(r"^mode\s+([a-zA-Z0-9_\-]+)\s*:\s*$", re.IGNORECASE)

    def parse(self, dsl_text: str) -> DSLParseResult:
        modes: dict[str, list[str]] = {}
        errors: list[str] = []

        current_mode: str | None = None
        for index, raw_line in enumerate(dsl_text.splitlines(), start=1):
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            mode_match = self._MODE_RE.match(stripped)
            if mode_match:
                current_mode = mode_match.group(1).lower()
                if current_mode in modes:
                    errors.append(f"Line {index}: duplicate mode '{current_mode}'")
                    current_mode = None
                else:
                    modes[current_mode] = []
                continue

            if current_mode is None:
                errors.append(f"Line {index}: command outside mode block")
                continue

            if not raw_line.startswith((" ", "\t")):
                errors.append(f"Line {index}: command must be indented under mode '{current_mode}'")
                continue
            modes[current_mode].append(stripped)

        return DSLParseResult(modes=modes, errors=errors)

