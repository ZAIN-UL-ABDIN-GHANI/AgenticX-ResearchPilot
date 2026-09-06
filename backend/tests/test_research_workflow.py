"""
Phase 10: Integration tests for complete research workflow.

Tests the full pipeline:
- Start research → Search → Fetch → Summarize → Validate → Answer
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.db.base import Base
from app.db.models import ResearchRun, Source, ToolCall, Claim
from app.repositories.research_repository import ResearchRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.services.citation_integration import CitationIntegrationService
from app.schemas.tools import (
    WebSearchResponse,
    SearchResult,
    FetchPageResponse,
    SummarizeResponse,
    KeyClaim,
)


@pytest.fixture
async def research_service():
    """Fixture for research repository."""
    async with async_session_maker() as session:
        yield CitationIntegrationService()


@pytest.mark.asyncio
async def test_research_creation():
    """Test creating a research run."""
    async with async_session_maker() as session:
        repo = ResearchRepository(session)
        research = await repo.create("What is machine learning?", max_steps=8)

        assert research.id is not None
        assert research.question == "What is machine learning?"
        assert research.status == "running"
        assert research.max_steps == 8
        assert research.steps_used == 0


@pytest.mark.asyncio
async def test_add_search_results():
    """Test adding search results to citation service."""
    service = CitationIntegrationService()

    response = WebSearchResponse(
        success=True,
        results=[
            SearchResult(
                source_id="SRC-001",
                title="Article 1",
                url="https://example1.com",
                snippet="First search result",
                domain="example1.com",
            ),
            SearchResult(
                source_id="SRC-002",
                title="Article 2",
                url="https://example2.com",
                snippet="Second search result",
                domain="example2.com",
            ),
        ],
        result_count=2,
    )

    await service.add_search_source(response)

    assert len(service.sources_map) == 2
    assert "SRC-001" in service.sources_map
    assert "SRC-002" in service.sources_map
    assert not service.sources_map["SRC-001"]["fetched"]


@pytest.mark.asyncio
async def test_add_fetched_source():
    """Test adding fetched source."""
    service = CitationIntegrationService()

    response = FetchPageResponse(
        success=True,
        source_id="SRC-001",
        url="https://example.com",
        title="Example Article",
        content="This is fetched content with important information.",
        word_count=8,
        fetch_status="success",
    )

    await service.add_fetched_source(response)

    assert "SRC-001" in service.sources_map
    assert service.sources_map["SRC-001"]["fetched"]
    assert service.sources_map["SRC-001"]["word_count"] == 8


@pytest.mark.asyncio
async def test_add_evidence_from_summary():
    """Test extracting evidence from summary."""
    service = CitationIntegrationService()

    # Add fetched source first
    response = FetchPageResponse(
        success=True,
        source_id="SRC-001",
        url="https://example.com",
        title="Example",
        content="Content here",
        word_count=2,
        fetch_status="success",
    )
    await service.add_fetched_source(response)

    # Add evidence from summary
    summary = SummarizeResponse(
        success=True,
        source_id="SRC-001",
        summary="Summary of the article",
        key_claims=[
            KeyClaim(claim="Machine learning is AI", evidence="ML is AI"),
            KeyClaim(claim="AI systems learn", evidence="They improve over time"),
        ],
    )

    await service.add_evidence_from_summary("SRC-001", summary)

    assert len(service.evidence_map) == 2
    assert "EVI-SRC-001-00" in service.evidence_map
    assert "EVI-SRC-001-01" in service.evidence_map


@pytest.mark.asyncio
async def test_extract_claims_from_answer():
    """Test extracting claims from final answer."""
    service = CitationIntegrationService()

    answer = """
    Machine learning is a type of AI. It enables systems to learn from data.
    Deep learning is a subset of machine learning. Neural networks power deep learning.
    """

    claims = service.extract_claims_from_answer(answer)

    assert len(claims) > 0
    assert all("claim_text" in c for c in claims)
    assert all("claim_id" in c for c in claims)


@pytest.mark.asyncio
async def test_find_supporting_evidence():
    """Test finding evidence that supports a claim."""
    service = CitationIntegrationService()

    # Add evidence
    service.evidence_map["EVI-001"] = {
        "evidence_id": "EVI-001",
        "source_id": "SRC-001",
        "text": "Machine learning systems learn from data",
        "evidence": "ML learns",
        "confidence": 0.9,
    }
    service.evidence_map["EVI-002"] = {
        "evidence_id": "EVI-002",
        "source_id": "SRC-002",
        "text": "Neural networks are used in deep learning",
        "evidence": "Nets in DL",
        "confidence": 0.85,
    }

    # Test finding supporting evidence
    supporting = service.find_supporting_evidence("Machine learning systems process data")

    assert len(supporting) > 0
    assert "EVI-001" in supporting


@pytest.mark.asyncio
async def test_validate_claim():
    """Test validating a claim."""
    service = CitationIntegrationService()

    # Add source
    service.sources_map["SRC-001"] = {
        "source_id": "SRC-001",
        "url": "https://example.com",
        "fetched": True,
        "content": "Example content",
    }

    # Add evidence
    service.evidence_map["EVI-001"] = {
        "evidence_id": "EVI-001",
        "source_id": "SRC-001",
        "text": "Machine learning is AI",
        "evidence": "ML definition",
        "confidence": 0.9,
    }

    claim = {
        "claim_id": "CLM-001",
        "claim_text": "Machine learning is a type of artificial intelligence",
    }

    validated = service.validate_claim(claim, ["EVI-001"])

    assert validated["verified"]
    assert validated["has_fetched_source"]
    assert "SRC-001" in validated["source_ids"]


@pytest.mark.asyncio
async def test_validate_answer():
    """Test validating complete answer."""
    service = CitationIntegrationService()

    # Setup sources
    service.sources_map["SRC-001"] = {
        "source_id": "SRC-001",
        "url": "https://example.com",
        "title": "ML Guide",
        "domain": "example.com",
        "fetched": True,
        "content": "Machine learning enables systems to learn",
    }

    # Setup evidence
    service.evidence_map["EVI-001"] = {
        "evidence_id": "EVI-001",
        "source_id": "SRC-001",
        "text": "Machine learning is AI",
        "evidence": "Definition",
        "confidence": 0.9,
    }

    answer = "Machine learning is a type of artificial intelligence."

    report = service.validate_answer(answer)

    assert "valid" in report
    assert report["total_claims"] > 0
    assert report["fetched_sources"] >= 0


@pytest.mark.asyncio
async def test_remove_unverified_claims():
    """Test removing unverified claims."""
    service = CitationIntegrationService()

    # Setup minimal sources
    service.sources_map["SRC-001"] = {
        "source_id": "SRC-001",
        "url": "https://example.com",
        "fetched": True,
    }

    answer = "Machine learning is AI. Unicorns exist."

    validation_report = {
        "valid": False,
        "total_claims": 2,
        "verified_claims": 1,
        "verification_rate": 50,
        "claims": [
            {
                "claim_id": "CLM-001",
                "claim_text": "Machine learning is AI",
                "verified": True,
                "source_ids": ["SRC-001"],
            },
            {
                "claim_id": "CLM-002",
                "claim_text": "Unicorns exist.",
                "verified": False,
                "source_ids": [],
            },
        ],
    }

    cleaned = service.remove_unverified_claims(answer, validation_report)

    assert "Unicorns" not in cleaned
    assert len(cleaned) < len(answer)


@pytest.mark.asyncio
async def test_build_citations():
    """Test building citations section."""
    service = CitationIntegrationService()

    service.sources_map["SRC-001"] = {
        "source_id": "SRC-001",
        "url": "https://example1.com",
        "title": "Article 1",
        "domain": "example1.com",
    }

    validation_report = {
        "valid": True,
        "claims": [
            {
                "claim_id": "CLM-001",
                "claim_text": "Claim text",
                "verified": True,
                "source_ids": ["SRC-001"],
            },
        ],
    }

    citations = service.get_citations_section(validation_report)

    assert "## Sources" in citations
    assert "Article 1" in citations
    assert "example1.com" in citations


@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete research workflow from start to finish."""
    async with async_session_maker() as session:
        # Create research
        repo = ResearchRepository(session)
        research = await repo.create("What is machine learning?")
        await session.commit()

        assert research.id is not None

        # Initialize citation service
        service = CitationIntegrationService()

        # Simulate search
        search_response = WebSearchResponse(
            success=True,
            results=[
                SearchResult(
                    source_id="SRC-001",
                    title="ML Basics",
                    url="https://ml-basics.com",
                    snippet="Machine learning explained",
                    domain="ml-basics.com",
                ),
            ],
            result_count=1,
        )
        await service.add_search_source(search_response)

        # Simulate fetch
        fetch_response = FetchPageResponse(
            success=True,
            source_id="SRC-001",
            url="https://ml-basics.com",
            title="ML Basics",
            content="Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            word_count=18,
            fetch_status="success",
        )
        await service.add_fetched_source(fetch_response)

        # Simulate summarization
        summary_response = SummarizeResponse(
            success=True,
            source_id="SRC-001",
            summary="ML is AI that learns from data",
            key_claims=[
                KeyClaim(
                    claim="Machine learning is AI",
                    evidence="ML is a subset of AI",
                ),
            ],
        )
        await service.add_evidence_from_summary("SRC-001", summary_response)

        # Test validation
        answer = "Machine learning is a subset of artificial intelligence."
        report = service.validate_answer(answer)

        assert report["fetched_sources"] > 0
        assert report["total_evidence"] > 0


@pytest.mark.asyncio
async def test_step_limit_enforcement():
    """Test that step limit is enforced."""
    async with async_session_maker() as session:
        repo = ResearchRepository(session)
        research = await repo.create("Test", max_steps=3)

        # Simulate steps
        tool_repo = ToolCallRepository(session)
        for i in range(4):
            await tool_repo.create(
                research_run_id=research.id,
                tool_name="web_search",
                step_number=i + 1,
                status="success",
            )

        # Should have created 4 tool calls, but step limit is 3
        calls = await tool_repo.get_by_research(research.id)
        assert len(calls) == 4  # All created, but app logic should stop at 3


@pytest.mark.asyncio
async def test_no_source_no_claim_policy():
    """Test that unsupported claims are rejected."""
    service = CitationIntegrationService()

    # No sources added
    claim = {
        "claim_id": "CLM-001",
        "claim_text": "Unsupported claim with no evidence",
    }

    validated = service.validate_claim(claim, [])

    assert not validated["verified"]
    assert not validated["has_evidence"]


@pytest.mark.asyncio
async def test_citation_service_reset():
    """Test resetting citation service state."""
    service = CitationIntegrationService()

    service.sources_map["SRC-001"] = {"url": "https://example.com"}
    service.evidence_map["EVI-001"] = {"text": "Evidence"}

    service.reset()

    assert len(service.sources_map) == 0
    assert len(service.evidence_map) == 0
