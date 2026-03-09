from __future__ import annotations

from pathlib import Path
from typing import Any

from nira.core.path_utils import PathSecurityError, resolve_within_root
from nira.tools.base import Tool, ToolResult


class CodeGenerator(Tool):
    name = "generate_code"
    description = "Generate local code or implementation notes using the local model."

    def __init__(self, model) -> None:
        self.model = model

    def run(self, args: dict[str, Any], state) -> ToolResult:
        instructions = str(args.get("instructions") or state.user_input).strip()
        context = getattr(state, "context", {}) or {}
        artifacts_dir = Path(str(context.get("artifacts_dir", Path.home() / ".nira" / "artifacts"))).expanduser().resolve()
        default_path = artifacts_dir / "generated_code.py"
        try:
            path = resolve_within_root(artifacts_dir, str(args.get("path", default_path)))
        except (PathSecurityError, OSError) as exc:
            return ToolResult(False, f"Invalid code output path: {exc}")
        prompt = (
            "Generate a concise local implementation artifact.\n"
            f"Intent: {state.intent}\n"
            f"Context: {context}\n"
            f"Instructions: {instructions}\n"
        )
        try:
            generated = self.model.generate(prompt).text if self.model else ""
        except Exception as exc:
            return ToolResult(False, f"Code generation failed: {exc}")
        if not generated:
            generated = "# Local generation fallback\n" + instructions + "\n"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(generated, encoding="utf-8")
        except OSError as exc:
            return ToolResult(False, f"Could not write generated code: {exc}")
        return ToolResult(True, f"Generated code artifact at {path}", {"path": str(path), "preview": generated[:200]})
