"""
Web research using duckduckgo-search library.

WHY THIS REPLACES THE OLD VERSION:
  The old version scraped DuckDuckGo's HTML page directly.
  DDG changes its HTML structure frequently and actively blocks scrapers.
  This broke web search entirely — always returning "No results found".

  Fix: use the `duckduckgo-search` pip package (DDGS class) which calls
  DDG's internal API. No API key required. Reliable. Free.

INSTALL:
  pip install duckduckgo-search==6.3.7
"""

import asyncio
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from bot.tools.base import Tool, ToolResult

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PAGE_TIMEOUT = aiohttp.ClientTimeout(total=8)


class ResearchTool(Tool):
    name = "web_research"
    description = (
        "Search the web and extract information from pages. "
        "Good for finding company info, pricing, news, or any factual research."
    )

    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "num_results": {
                "type": "integer",
                "default": 3,
                "description": "Number of results to fetch (max 5)",
            },
            "extract_content": {
                "type": "boolean",
                "default": True,
                "description": "Whether to fetch and summarise page content",
            },
        },
        "required": ["query"],
    }

    async def _fetch_page_text(
        self, session: aiohttp.ClientSession, url: str
    ) -> str:
        """Fetch a URL and return cleaned plain text (first 1000 chars)."""
        try:
            async with session.get(
                url, headers=HEADERS, timeout=PAGE_TIMEOUT, ssl=False
            ) as resp:
                if resp.status != 200:
                    return f"[HTTP {resp.status}]"
                html = await resp.text(errors="replace")
                soup = BeautifulSoup(html, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                return soup.get_text(separator=" ", strip=True)[:1000]
        except asyncio.TimeoutError:
            return "[Page timed out]"
        except Exception as exc:
            return f"[Could not extract: {exc}]"

    def _ddg_search(self, query: str, num_results: int) -> list[dict]:
        """
        Run DDGS search in a thread (it's synchronous).
        Returns list of {title, url, snippet}.
        """
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results

    async def execute(
        self,
        query: str,
        num_results: int = 3,
        extract_content: bool = True,
    ) -> ToolResult:

        num_results = min(max(num_results, 1), 5)

        try:
            # DDGS is synchronous — run in thread pool to avoid blocking event loop
            parsed = await asyncio.to_thread(self._ddg_search, query, num_results)

            if not parsed:
                return ToolResult(
                    status="error",
                    message=f"No results found for: '{query}'",
                    error="zero_results",
                    retryable=True,
                )

            # Optionally fetch full page content in parallel
            if extract_content:
                async with aiohttp.ClientSession() as session:
                    tasks = [
                        self._fetch_page_text(session, r["url"])
                        for r in parsed
                        if r["url"]
                    ]
                    previews = await asyncio.gather(*tasks)
                    for item, preview in zip(parsed, previews):
                        item["content_preview"] = preview

            return ToolResult(
                status="success",
                message=f"Found {len(parsed)} results for '{query}'",
                data={"query": query, "results": parsed},
            )

        except Exception as exc:
            return ToolResult(
                status="error",
                message=f"Research failed: {exc}",
                error=str(exc),
                retryable=True,
            )
