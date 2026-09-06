"""Research API request and response schemas."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ResearchCreateRequest(BaseModel):
    """Request to start research."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Research question"
    )
    max_steps: Optional[int] = Field(
        default=8,
        ge=1,
        le=50,
        description="Maximum research steps (hard limit)"
    )


class ResearchResponse(BaseModel):
    """Response when research is created."""

    research_id: str
    question: str
    status: str
    max_steps: int
    created_at: str


class ResearchStatusResponse(BaseModel):
    """Complete research status response."""

    research_id: str
    question: str
    status: str
    max_steps: int
    steps_used: int
    final_answer: Optional[str]
    created_at: str
    completed_at: Optional[str]

    class Config:
        json_schema_extra = {
            "example": {
                "research_id": "1",
                "question": "What is RAG?",
                "status": "completed",
                "max_steps": 8,
                "steps_used": 6,
                "final_answer": "RAG is Retrieval-Augmented Generation...",
                "created_at": "2026-09-02T10:00:00",
                "completed_at": "2026-09-02T10:05:00",
            }
        }


class SourceResponse(BaseModel):
    """Single source in research."""

    source_id: str
    url: str
    title: Optional[str]
    domain: Optional[str]
    fetch_status: str
    word_count: Optional[int]
    fetched_at: Optional[str]


class SourceListResponse(BaseModel):
    """Response with list of sources."""

    research_id: str
    total_sources: int
    sources: List[SourceResponse]


class ToolCallResponse(BaseModel):
    """Single tool call record."""

    step_number: Optional[int]
    tool_name: str
    status: str
    input: Optional[Dict[str, Any]]
    output: Optional[Dict[str, Any]]
    created_at: str


class ToolCallListResponse(BaseModel):
    """Response with list of tool calls."""

    research_id: str
    total_calls: int
    tool_calls: List[ToolCallResponse]


class CitationResponse(BaseModel):
    """Citation for a claim."""

    source_id: Optional[str]
    url: Optional[str]
    title: Optional[str]
    citation_number: Optional[int]
    confidence: Optional[int]
    evidence: Optional[str]


class ClaimResponse(BaseModel):
    """Single claim with citations."""

    claim_id: int
    claim_text: str
    citations: List[CitationResponse]


class ClaimListResponse(BaseModel):
    """Response with list of claims."""

    research_id: str
    total_claims: int
    claims: List[ClaimResponse]
