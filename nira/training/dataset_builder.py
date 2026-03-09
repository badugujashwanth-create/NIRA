from __future__ import annotations

import json
from pathlib import Path


class DatasetBuilder:
    def __init__(self, interaction_log: Path) -> None:
        self.interaction_log = Path(interaction_log)

    def build(self, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        if self.interaction_log.exists():
            for line in self.interaction_log.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows.append(
                    {
                        "instruction": payload.get("input", ""),
                        "response": payload.get("response", ""),
                        "metadata": payload.get("intent", {}),
                    }
                )
        body = "\n".join(json.dumps(row, ensure_ascii=True) for row in rows)
        output_path.write_text((body + "\n") if body else "", encoding="utf-8")
        return output_path
