"""
Web research using aiohttp + BeautifulSoup.

BUG FIXED:
  Previous version used the synchronous `requests` library inside an
  async function, blocking the entire event loop for every HTTP call.
  Replaced with `aiohttp` for true non-blocking I/O.
"""

import asyncio
from typing import Dict, Any, List
from urllib.parse import quote_plus

import aiohttp
from bs4 import BeautifulSoup

from bot.tools.base import Tool, ToolResult

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# How long to wait for DuckDuckGo / individual pages
SEARCH_TIMEOUT = aiohttp.ClientTimeout(total=12)
PAGE_TIMEOUT = aiohttp.ClientTimeout(total=6)


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
        """Fetch a URL and return cleaned plain text (first 1 000 chars)."""
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

    async def execute(
        self,
        query: str,
        num_results: int = 3,
        extract_content: bool = True,
    ) -> ToolResult:

        num_results = min(max(num_results, 1), 5)

        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            async with aiohttp.ClientSession() as session:
                # ── 1. Fetch search results ──────────────────────────────
                async with session.post(
                    search_url,
                    headers={**HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
                    timeout=SEARCH_TIMEOUT,
                ) as resp:
                    html_body = await resp.text(errors="replace")

                soup = BeautifulSoup(html_body, "html.parser")
                raw_results = soup.find_all("div", class_="result")[:num_results]

                if not raw_results:
                    return ToolResult(
                        status="error",
                        message="No results found. DuckDuckGo may have changed its HTML structure.",
                        error="zero_results",
                        retryable=True,
                    )

                # ── 2. Parse result cards ────────────────────────────────
                parsed: list[dict] = []
                for r in raw_results:
                    title_el = r.find("a", class_="result__a")
                    if not title_el:
                        continue
                    snippet_el = r.find("a", class_="result__snippet")
                    parsed.append(
                        {
                            "title": title_el.get_text(strip=True),
                            "url": title_el.get("href", ""),
                            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        }
                    )

                # ── 3. Optionally fetch page content in parallel ─────────
                if extract_content:
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
