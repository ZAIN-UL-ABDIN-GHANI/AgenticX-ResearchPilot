"""
Web page fetching and content extraction tool.
"""

import httpx
from typing import Optional
from bs4 import BeautifulSoup
import html2text

from app.schemas.tools import FetchPageRequest, FetchPageResponse
from app.utils.urls import is_safe_url
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_fetch_page_tool = None


class FetchPageTool:
    """Tool for fetching and cleaning web page content."""
    
    def __init__(self, timeout: int = 15, user_agent: str = ""):
        """Initialize the fetch page tool."""
        self.timeout = timeout
        self.user_agent = user_agent or settings.user_agent
    
    async def execute(
        self,
        url: str,
        source_id: str,
    ) -> FetchPageResponse:
        """
        Fetch and clean page content.
        
        Args:
            url: URL to fetch
            source_id: Source identifier
        
        Returns:
            FetchPageResponse with content or error
        """
        try:
            # Validate input
            request = FetchPageRequest(url=url, source_id=source_id)
            
            # Check for SSRF
            if not is_safe_url(request.url):
                logger.warning(f"Unsafe URL blocked: {request.url}")
                return FetchPageResponse(
                    success=False,
                    source_id=request.source_id,
                    url=request.url,
                    error="Forbidden URL",
                    fetch_status="forbidden",
                )
            
            # Fetch page
            response = await self._fetch(request.url)
            
            if response.status_code == 404:
                return FetchPageResponse(
                    success=False,
                    source_id=request.source_id,
                    url=request.url,
                    error="Page not found",
                    fetch_status="error",
                )
            elif response.status_code == 403:
                return FetchPageResponse(
                    success=False,
                    source_id=request.source_id,
                    url=request.url,
                    error="Access forbidden",
                    fetch_status="forbidden",
                )
            
            response.raise_for_status()
            
            # Extract title
            title = await self._extract_title(response)
            
            # Clean content
            content = await self._clean_content(response.text)
            
            # Count words
            word_count = len(content.split())
            
            logger.info(
                f"Page fetched successfully",
                extra={
                    "url": request.url,
                    "source_id": request.source_id,
                    "word_count": word_count,
                },
            )
            
            return FetchPageResponse(
                success=True,
                source_id=request.source_id,
                url=request.url,
                title=title,
                content=content,
                word_count=word_count,
                fetch_status="success",
            )
        
        except httpx.TimeoutException as e:
            logger.warning(f"Fetch timeout: {str(e)}")
            return FetchPageResponse(
                success=False,
                source_id=source_id,
                url=url,
                error="Timeout",
                fetch_status="timeout",
            )
        except httpx.HTTPError as e:
            logger.error(f"Fetch HTTP error: {str(e)}")
            return FetchPageResponse(
                success=False,
                source_id=source_id,
                url=url,
                error="Network error",
                fetch_status="error",
            )
        except Exception as e:
            logger.error(f"Fetch error: {str(e)}", exc_info=True)
            return FetchPageResponse(
                success=False,
                source_id=source_id,
                url=url,
                error="Unexpected error",
                fetch_status="error",
            )
    
    async def _fetch(self, url: str) -> httpx.Response:
        """Fetch page content."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                headers={"User-Agent": self.user_agent},
                follow_redirects=True,
            )
            return response
    
    async def _extract_title(self, response: httpx.Response) -> Optional[str]:
        """Extract title from HTML."""
        try:
            soup = BeautifulSoup(response.text, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                return title_tag.get_text(strip=True)
        except Exception:
            pass
        return None
    
    async def _clean_content(self, html: str) -> str:
        """Clean and extract text content from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # Remove script and style
            for tag in soup(["script", "style"]):
                tag.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Normalize whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = " ".join(chunk for chunk in chunks if chunk)
            
            return text[:100000]  # Limit to 100KB
        except Exception:
            # Fallback to html2text
            try:
                h = html2text.HTML2Text()
                h.ignore_links = False
                return h.handle(html)[:100000]
            except Exception:
                return ""


def get_fetch_page_tool() -> FetchPageTool:
    """Get or create fetch page tool singleton."""
    global _fetch_page_tool
    if _fetch_page_tool is None:
        _fetch_page_tool = FetchPageTool(
            timeout=settings.fetch_timeout,
            user_agent=settings.user_agent,
        )
    return _fetch_page_tool
