from __future__ import annotations

from dataclasses import asdict

from nira_core.retrieval import RetrievalPipeline
from nira_core.tools.base import ToolResult


class RetrievalTool:
    """Tool facade over the retrieval pipeline."""

    name = "retrieval"

    def __init__(self, retrieval: RetrievalPipeline) -> None:
        self._retrieval = retrieval

    async def run(self, payload: dict[str, object]) -> ToolResult:
        query = str(payload.get("query", ""))
        if not query:
            return ToolResult(False, error="missing_query")
        results = await self._retrieval.retrieve(query)
        return ToolResult(
            True,
            output="\n".join(item.text for item in results),
            data={"results": [asdict(item) for item in results]},
        )
