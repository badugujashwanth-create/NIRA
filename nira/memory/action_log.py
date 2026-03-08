from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nira.security.encryption import EncryptedActionLogger


class ActionLog:
    def __init__(self, encrypted_logger: EncryptedActionLogger) -> None:
        self._logger = encrypted_logger

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self._logger.write_event(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "payload": payload,
            }
        )

    def log_interaction(
        self,
        command: str,
        response: str,
        source: str,
        success: bool,
    ) -> None:
        self.log_event(
            "interaction",
            {
                "command": command,
                "response": response,
                "source": source,
                "success": success,
            },
        )

