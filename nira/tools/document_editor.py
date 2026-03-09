from __future__ import annotations

from typing import Any

from nira.tools.base import Tool, ToolResult


class DocumentEditorTool(Tool):
    name = "edit_document"
    description = "Create or update a local markdown, txt, or report document."

    def __init__(self, document_editor, report_generator) -> None:
        self.document_editor = document_editor
        self.report_generator = report_generator

    def run(self, args: dict[str, Any], state) -> ToolResult:
        path = args.get("path")
        content = str(args.get("content", "")).strip()
        try:
            if path:
                target = self.document_editor.write(str(path), content)
                return ToolResult(True, f"Updated document {target}", {"path": str(target)})
            target = self.report_generator.write_markdown("runtime_notes.md", content or state.user_input)
            return ToolResult(True, f"Updated report {target}", {"path": str(target)})
        except (OSError, ValueError) as exc:
            return ToolResult(False, f"Document edit failed: {exc}")
