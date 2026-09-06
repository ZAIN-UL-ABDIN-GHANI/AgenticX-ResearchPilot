"""
Repository for claims and claim_sources table operations.

Implements the mandatory traceability chain:
    Claim -> ClaimSource (evidence + citation_number) -> Source -> fetched content -> URL
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Claim, ClaimSource, Source
from app.core.logging import get_logger

logger = get_logger(__name__)


class ClaimRepository:
    """Repository for claim and citation data access."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def create_claim(self, research_run_id: int, claim_text: str) -> Claim:
        """Create a new claim row.

        Rule: this should only be called for claims that have already been
        verified against a fetched source (NO SOURCE = NO CLAIM). Verification
        happens upstream in CitationIntegrationService.
        """
        claim = Claim(research_run_id=research_run_id, claim_text=claim_text)
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def add_citation(
        self,
        claim_id: int,
        source_id: int,
        evidence: Optional[str],
        citation_number: Optional[int],
        confidence: Optional[float] = None,
    ) -> ClaimSource:
        """Link a claim to a fetched source with evidence and a citation number."""
        confidence_pct = int(round(confidence * 100)) if confidence is not None else None
        claim_source = ClaimSource(
            claim_id=claim_id,
            source_id=source_id,
            evidence=evidence,
            citation_number=citation_number,
            confidence=confidence_pct,
        )
        self.session.add(claim_source)
        await self.session.flush()
        return claim_source

    async def get_by_research(self, research_run_id: int) -> List[Claim]:
        """Get all claims (with citations eagerly loaded) for a research run."""
        result = await self.session.execute(
            select(Claim)
            .where(Claim.research_run_id == research_run_id)
            .options(
                selectinload(Claim.claim_sources).selectinload(ClaimSource.source)
            )
        )
        return result.scalars().all()
