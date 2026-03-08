from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Intent:
    kind: str
    action: str
    args: dict[str, Any] = field(default_factory=dict)
    dangerous: bool = False
    provided_passphrase: Optional[str] = None


class IntentParser:
    _PASS_RE = re.compile(r"\bpassphrase\s+([^\s]+)\s*$", re.IGNORECASE)

    def parse(self, text: str) -> Intent:
        cleaned = text.strip()
        if not cleaned:
            return Intent(kind="none", action="none")

        cleaned, passphrase = self._extract_passphrase(cleaned)
        lowered = cleaned.lower()

        open_match = re.match(r"^(?:open|launch|start)\s+(.+)$", lowered)
        if open_match:
            target = cleaned[open_match.start(1) :].strip()
            return Intent(
                kind="automation",
                action="open_app",
                args={"target": target},
                provided_passphrase=passphrase,
            )

        close_match = re.match(r"^(?:close|quit|kill)\s+(.+)$", lowered)
        if close_match:
            target = cleaned[close_match.start(1) :].strip()
            return Intent(
                kind="automation",
                action="close_app",
                args={"target": target},
                dangerous=True,
                provided_passphrase=passphrase,
            )

        folder_match = re.match(r"^create\s+folder\s+(.+)$", lowered)
        if folder_match:
            path = cleaned[folder_match.start(1) :].strip().strip('"')
            return Intent(
                kind="automation",
                action="create_folder",
                args={"path": path},
                provided_passphrase=passphrase,
            )

        move_match = re.match(r"^move\s+file\s+(.+)\s+to\s+(.+)$", cleaned, re.IGNORECASE)
        if move_match:
            src = move_match.group(1).strip().strip('"')
            dst = move_match.group(2).strip().strip('"')
            return Intent(
                kind="automation",
                action="move_file",
                args={"src": src, "dst": dst},
                provided_passphrase=passphrase,
            )

        volume_match = re.match(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})$", lowered)
        if volume_match:
            return Intent(
                kind="automation",
                action="set_volume",
                args={"percent": int(volume_match.group(1))},
                provided_passphrase=passphrase,
            )

        workflow_match = re.match(r"^(?:run|start)\s+mode\s+([a-zA-Z0-9_\-]+)$", lowered)
        if workflow_match:
            return Intent(
                kind="workflow",
                action="run_mode",
                args={"mode": workflow_match.group(1)},
                provided_passphrase=passphrase,
            )

        if lowered in {"undo", "undo last action"}:
            return Intent(kind="automation", action="undo", provided_passphrase=passphrase)

        return Intent(kind="llm", action="chat", args={"prompt": cleaned}, provided_passphrase=passphrase)

    def _extract_passphrase(self, text: str) -> tuple[str, Optional[str]]:
        match = self._PASS_RE.search(text)
        if not match:
            return text, None
        passphrase = match.group(1).strip()
        stripped = self._PASS_RE.sub("", text).strip()
        return stripped, passphrase

