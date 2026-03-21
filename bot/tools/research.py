"""
Web research using requests + BeautifulSoup.
Lightweight alternative to heavy scraping frameworks.
"""

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List
from urllib.parse import quote_plus
from bot.tools.base import Tool, ToolResult

class ResearchTool(Tool):
    """Web research and scraping."""
    
    name = "web_research"
    description = "Search the web and extract information from pages."
    
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "num_results": {
                "type": "integer",
                "default": 3,
                "description": "Number of results to fetch (max 5)"
            },
            "extract_content": {
                "type": "boolean",
                "default": True,
                "description": "Whether to extract page content"
            }
        },
        "required": ["query"]
    }
    
    async def execute(
        self,
        query: str,
        num_results: int = 3,
        extract_content: bool = True
    ) -> ToolResult:
        try:
            # Limit results
            num_results = min(num_results, 5)
            
            # Search using DuckDuckGo HTML (no API key needed)
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0"
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for result in soup.find_all('div', class_='result')[:num_results]:
                title_elem = result.find('a', class_='result__a')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                snippet_elem = result.find('a', class_='result__snippet')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                
                result_data = {
                    "title": title,
                    "url": url,
                    "snippet": snippet
                }
                
                # Optionally extract page content
                if extract_content and url:
                    try:
                        page = requests.get(url, headers=headers, timeout=5)
                        page_soup = BeautifulSoup(page.text, 'html.parser')
                        
                        # Remove script/style
                        for script in page_soup(["script", "style"]):
                            script.decompose()
                        
                        text = page_soup.get_text(separator=' ', strip=True)
                        # Limit to first 1000 chars
                        result_data["content_preview"] = text[:1000]
                    except:
                        result_data["content_preview"] = "Could not extract content"
                
                results.append(result_data)
            
            return ToolResult(
                status="success",
                message=f"Found {len(results)} results for '{query}'",
                data={
                    "query": query,
                    "results": results
                }
            )
            
        except Exception as e:
            return ToolResult(
                status="error",
                message=f"Research failed: {str(e)}",
                error=str(e),
                retryable=True
            )
