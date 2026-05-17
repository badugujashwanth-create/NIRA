from __future__ import annotations

from nira_core.tools.base import ToolResult


class LocalAPITool:
    """Tool for calling explicitly configured local HTTP APIs."""

    name = "local_api"

    async def run(self, payload: dict[str, object]) -> ToolResult:
        try:
            import httpx
        except ImportError:
            return ToolResult(False, error="httpx_not_installed")
        method = str(payload.get("method", "GET")).upper()
        url = str(payload.get("url", ""))
        if not url.startswith(("http://127.0.0.1", "http://localhost")):
            return ToolResult(False, error="only_local_api_urls_allowed")
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, json=payload.get("json"))
        return ToolResult(response.is_success, output=response.text, data={"status_code": response.status_code})
