"""
Web search tool using Google Custom Search API.
"""

import httpx
from typing import Optional, List, Dict, Any
from app.schemas.tools import WebSearchRequest, WebSearchResponse, SearchResult
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_web_search_tool = None


class WebSearchTool:
    """Tool for searching the web using Google Custom Search."""
    
    def __init__(self, api_key: str, search_engine_id: str, timeout: int = 10):
        """Initialize the web search tool."""
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.timeout = timeout
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self._source_counter = 0
    
    async def execute(
        self,
        query: str,
        max_results: int = 5,
    ) -> WebSearchResponse:
        """
        Execute a web search.
        
        Args:
            query: Search query
            max_results: Maximum number of results (1-20)
        
        Returns:
            WebSearchResponse with results or error
        """
        try:
            # Validate input
            request = WebSearchRequest(query=query, max_results=max_results)
            
            # Execute search
            results = await self._search(request.query, request.max_results)
            
            logger.info(
                f"Web search completed",
                extra={
                    "query": request.query,
                    "results_count": len(results),
                },
            )
            
            return WebSearchResponse(
                success=True,
                results=results,
                result_count=len(results),
            )
        
        except httpx.TimeoutException as e:
            logger.warning(f"Web search timeout: {str(e)}")
            return WebSearchResponse(
                success=False,
                error="Search timeout",
            )
        except httpx.HTTPError as e:
            logger.error(f"Web search HTTP error: {str(e)}")
            return WebSearchResponse(
                success=False,
                error="API error",
            )
        except Exception as e:
            logger.error(f"Web search error: {str(e)}", exc_info=True)
            return WebSearchResponse(
                success=False,
                error="Unexpected error",
            )
    
    async def _search(self, query: str, max_results: int) -> List[SearchResult]:
        """Execute the actual search API call."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                self.base_url,
                params={
                    "q": query,
                    "key": self.api_key,
                    "cx": self.search_engine_id,
                    "num": max_results,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        results = []
        for i, item in enumerate(data.get("items", []), 1):
            self._source_counter += 1
            source_id = f"SRC-{self._source_counter:03d}"
            
            # Extract domain
            from urllib.parse import urlparse
            domain = urlparse(item.get("link", "")).netloc
            
            results.append(
                SearchResult(
                    source_id=source_id,
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    domain=domain,
                )
            )
        
        return results


def get_web_search_tool() -> WebSearchTool:
    """Get or create web search tool singleton."""
    global _web_search_tool
    if _web_search_tool is None:
        _web_search_tool = WebSearchTool(
            api_key=settings.search_api_key,
            search_engine_id=settings.search_engine_id,
            timeout=settings.search_timeout,
        )
    return _web_search_tool
