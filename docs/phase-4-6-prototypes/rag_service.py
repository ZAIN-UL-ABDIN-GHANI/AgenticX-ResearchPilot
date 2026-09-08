"""
RAG Service - High-level service for RAG pipeline integration.

Integrates RAG pipeline with:
- Source repositories
- Tool results
- Evidence storage
- Research run tracking
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import asdict

from rag_pipeline import (
    RAGPipeline,
    SourceEvidence,
    Evidence,
    Claim,
)

logger = logging.getLogger(__name__)


class RAGService:
    """Service for managing RAG operations in research workflow."""

    def __init__(self):
        """Initialize RAG service."""
        self.rag_pipeline = RAGPipeline(chunk_size=500, overlap=50)
        self.claims: Dict[str, Claim] = {}
        self.claim_counter = 0

    def process_fetched_source(
        self,
        source_id: str,
        url: str,
        content: str,
        title: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> SourceEvidence:
        """Process a fetched source through RAG pipeline.

        Args:
            source_id: Source identifier (SRC-001, etc.)
            url: Source URL
            content: Fetched page content
            title: Page title
            domain: Domain name

        Returns:
            Processed SourceEvidence with extracted evidence
        """
        logger.info(f"Processing source {source_id} through RAG pipeline")

        source_evidence = self.rag_pipeline.process_source(
            source_id=source_id,
            url=url,
            content=content,
            title=title,
            domain=domain,
        )

        if source_evidence.processing_status != "indexed":
            logger.warning(
                f"Source {source_id} processing failed: {source_evidence.processing_status}"
            )
            return source_evidence

        logger.info(
            f"Successfully processed {source_id}: "
            f"{len(source_evidence.evidence_list)} evidence items extracted"
        )

        return source_evidence

    def create_claim(
        self, claim_text: str, research_run_id: Optional[int] = None
    ) -> Claim:
        """Create a new factual claim.

        Args:
            claim_text: The claim statement
            research_run_id: Associated research run ID

        Returns:
            Claim object
        """
        claim_id = f"CLM-{self.claim_counter:04d}"
        self.claim_counter += 1

        claim = Claim(
            claim_id=claim_id,
            text=claim_text,
            research_run_id=research_run_id,
            evidence_ids=[],
            has_source=False,
            verified=False,
        )

        self.claims[claim_id] = claim
        logger.debug(f"Created claim {claim_id}: {claim_text[:50]}...")

        return claim

    def link_evidence_to_claim(
        self, claim_id: str, evidence_id: str
    ) -> bool:
        """Link evidence to a claim.

        Args:
            claim_id: Claim identifier
            evidence_id: Evidence identifier

        Returns:
            True if successful
        """
        if claim_id not in self.claims:
            logger.warning(f"Claim {claim_id} not found")
            return False

        claim = self.claims[claim_id]

        if evidence_id not in claim.evidence_ids:
            claim.evidence_ids.append(evidence_id)
            claim.has_source = True
            logger.debug(f"Linked {evidence_id} to {claim_id}")

        return True

    def verify_claim(self, claim_id: str) -> bool:
        """Verify a claim has supporting evidence.

        Args:
            claim_id: Claim identifier

        Returns:
            True if claim has source evidence
        """
        if claim_id not in self.claims:
            return False

        claim = self.claims[claim_id]
        if not claim.evidence_ids:
            return False

        # Get all evidence for this claim
        all_evidence = self.rag_pipeline.get_all_evidence()
        evidence_map = {e.evidence_id: e for e in all_evidence}

        # Check that at least one evidence exists and was fetched
        has_verified_evidence = any(
            evidence_map.get(eid, Evidence("", "", "")).is_verified
            or evidence_map.get(eid, Evidence("", "", "")).text
            for eid in claim.evidence_ids
            if eid in evidence_map
        )

        claim.verified = has_verified_evidence
        return has_verified_evidence

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Get a claim by ID.

        Args:
            claim_id: Claim identifier

        Returns:
            Claim or None
        """
        return self.claims.get(claim_id)

    def get_claims_summary(self) -> Dict[str, Any]:
        """Get summary of all claims and their evidence.

        Returns:
            Summary dictionary
        """
        claims_data = []
        for claim_id, claim in self.claims.items():
            all_evidence = self.rag_pipeline.get_all_evidence()
            evidence_map = {e.evidence_id: e for e in all_evidence}

            evidence_items = [
                asdict(evidence_map[eid])
                for eid in claim.evidence_ids
                if eid in evidence_map
            ]

            claims_data.append({
                "claim_id": claim_id,
                "text": claim.text,
                "has_source": claim.has_source,
                "verified": claim.verified,
                "evidence_count": len(claim.evidence_ids),
                "evidence": evidence_items,
            })

        return {
            "total_claims": len(self.claims),
            "claims": claims_data,
        }

    def search_evidence_for_query(self, query: str) -> List[Evidence]:
        """Search evidence matching a query.

        Args:
            query: Search query

        Returns:
            List of matching Evidence objects
        """
        return self.rag_pipeline.search_evidence(query)

    def get_sources_summary(self) -> Dict[str, Any]:
        """Get summary of all processed sources.

        Returns:
            Summary dictionary
        """
        return self.rag_pipeline.get_processed_sources_summary()

    def reset(self) -> None:
        """Reset service state (for testing)."""
        self.rag_pipeline = RAGPipeline(chunk_size=500, overlap=50)
        self.claims = {}
        self.claim_counter = 0
        logger.info("RAG service reset")


class RAGEvidenceMapper:
    """Maps evidence to sources and ensures traceability."""

    @staticmethod
    def build_evidence_chain(
        claim: Claim,
        evidence_items: List[Evidence],
        sources: Dict[str, SourceEvidence],
    ) -> Dict[str, Any]:
        """Build complete evidence chain for a claim.

        Chain: Claim → Evidence → Source → Fetched Content

        Args:
            claim: The claim
            evidence_items: Evidence supporting claim
            sources: Processed sources

        Returns:
            Evidence chain mapping
        """
        chain = {
            "claim_id": claim.claim_id,
            "claim_text": claim.text,
            "total_evidence": len(evidence_items),
            "evidence_chain": [],
            "is_traceable": True,
        }

        for evidence in evidence_items:
            source = sources.get(evidence.source_id)

            if not source:
                chain["is_traceable"] = False
                logger.warning(
                    f"Source {evidence.source_id} not found for {evidence.evidence_id}"
                )
                continue

            if not source.fetched_content:
                chain["is_traceable"] = False
                logger.warning(
                    f"No fetched content for {evidence.source_id}"
                )
                continue

            chain["evidence_chain"].append({
                "evidence_id": evidence.evidence_id,
                "evidence_text": evidence.text,
                "confidence": evidence.confidence,
                "source_id": evidence.source_id,
                "source_url": source.url,
                "source_title": source.title,
                "source_domain": source.domain,
                "evidence_found_in_content": evidence.text in source.fetched_content,
            })

        return chain

    @staticmethod
    def validate_evidence_chain(chain: Dict[str, Any]) -> bool:
        """Validate that evidence chain is complete and traceable.

        Args:
            chain: Evidence chain from build_evidence_chain

        Returns:
            True if chain is valid
        """
        if not chain.get("is_traceable"):
            return False

        if not chain.get("evidence_chain"):
            return False

        # All evidence must be found in source content
        for evidence_item in chain["evidence_chain"]:
            if not evidence_item.get("evidence_found_in_content"):
                return False

        return True
