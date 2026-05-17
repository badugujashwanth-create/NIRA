from __future__ import annotations

from nira_core.tools.base import ToolResult


class BrowserTool:
    """Async Playwright browser automation tool."""

    name = "browser"

    async def run(self, payload: dict[str, object]) -> ToolResult:
        """Navigate, extract content, and optionally fill a simple form."""

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return ToolResult(False, error="playwright_not_installed")

        url = str(payload.get("url", ""))
        if not url:
            return ToolResult(False, error="missing_url")
        selector = str(payload.get("selector", "body"))
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
                fills = payload.get("fill", {})
                if isinstance(fills, dict):
                    for target, value in fills.items():
                        await page.fill(str(target), str(value), timeout=5_000)
                content = await page.locator(selector).inner_text(timeout=10_000)
                await browser.close()
            return ToolResult(True, output=content, data={"url": url, "selector": selector})
        except Exception as exc:
            return ToolResult(False, error=str(exc), data={"url": url, "selector": selector})
