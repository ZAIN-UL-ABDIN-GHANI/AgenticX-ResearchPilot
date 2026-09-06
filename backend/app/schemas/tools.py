"""
Pydantic schemas for research tools.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class WebSearchRequest(BaseModel):
    """Web search tool request."""
    
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=20)
    
    @validator("query")
    def query_must_be_stripped(cls, v):
        return v.strip()


class SearchResult(BaseModel):
    """Individual search result."""
    
    source_id: str
    title: str
    url: str
    snippet: str
    domain: Optional[str] = None


class WebSearchResponse(BaseModel):
    """Web search tool response."""
    
    success: bool
    results: List[SearchResult] = []
    error: Optional[str] = None
    result_count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "results": [
                    {
                        "source_id": "SRC-001",
                        "title": "Example Article",
                        "url": "https://example.com",
                        "snippet": "First 160 characters...",
                        "domain": "example.com"
                    }
                ],
                "result_count": 1
            }
        }


class FetchPageRequest(BaseModel):
    """Fetch page tool request."""
    
    url: str = Field(...)
    source_id: str = Field(...)
    
    @validator("url")
    def url_must_be_http(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class FetchPageResponse(BaseModel):
    """Fetch page tool response."""
    
    success: bool
    source_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    word_count: Optional[int] = None
    error: Optional[str] = None
    fetch_status: str = "pending"  # pending, success, timeout, error, forbidden

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "source_id": "SRC-001",
                "url": "https://example.com",
                "title": "Example Page",
                "content": "Page content here...",
                "word_count": 500,
                "fetch_status": "success"
            }
        }


class KeyClaim(BaseModel):
    """Key claim extracted from content."""
    
    claim: str
    evidence: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SummarizeRequest(BaseModel):
    """Summarization tool request."""
    
    source_id: str
    content: str = Field(..., min_length=100, max_length=100000)
    context: Optional[str] = None


class SummarizeResponse(BaseModel):
    """Summarization tool response."""
    
    success: bool
    source_id: Optional[str] = None
    summary: Optional[str] = None
    key_claims: List[KeyClaim] = []
    error: Optional[str] = None


class ToolResult(BaseModel):
    """Generic tool result for logging."""
    
    tool_name: str
    success: bool
    input_data: Optional[dict] = None
    output_data: Optional[dict] = None
    error: Optional[str] = None
    status: str = "success"
