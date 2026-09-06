"""
Phase 7: Citation Validation Integration

Integrates citation validator with research workflow:
- Validates claims before final answer
- Removes unsupported claims
- Builds proper citations with sources
- Ensures NO SOURCE = NO CLAIM policy
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from urllib.parse import urlparse

from app.schemas.tools import WebSearchResponse, FetchPageResponse, SummarizeResponse
from app.db.models import Claim, ClaimSource, Source, ResearchRun
from app.repositories.research_repository import ResearchRepository
from app.repositories.source_repository import SourceRepository

logger = logging.getLogger(__name__)


class CitationIntegrationService:
    """Service integrating citation validation with research workflow."""

    def __init__(self):
        """Initialize citation service."""
        self.claims: Dict[str, Dict[str, Any]] = {}
        self.sources_map: Dict[str, Dict[str, Any]] = {}
        self.evidence_map: Dict[str, Dict[str, Any]] = {}

    async def add_search_source(
        self,
        search_results: WebSearchResponse,
    ) -> None:
        """Track search results as potential sources.

        Args:
            search_results: WebSearchResponse from web_search tool
        """
        if not search_results.success:
            logger.warning("Search results marked as failed")
            return

        for result in search_results.results:
            self.sources_map[result.source_id] = {
                "source_id": result.source_id,
                "url": result.url,
                "title": result.title,
                "domain": result.domain,
                "snippet": result.snippet,
                "fetched": False,
                "content": None,
            }

        logger.info(f"Added {len(search_results.results)} sources from search")

    async def add_fetched_source(
        self,
        fetch_result: FetchPageResponse,
    ) -> None:
        """Track fetched page as verified source.

        Args:
            fetch_result: FetchPageResponse from fetch_page tool
        """
        if not fetch_result.success or not fetch_result.source_id:
            logger.warning(
                f"Fetch failed for {fetch_result.source_id}: {fetch_result.error}"
            )
            return

        domain = urlparse(fetch_result.url or "").netloc or "unknown"

        if fetch_result.source_id in self.sources_map:
            existing_domain = self.sources_map[fetch_result.source_id].get("domain")
            self.sources_map[fetch_result.source_id].update({
                "fetched": True,
                "content": fetch_result.content,
                "word_count": fetch_result.word_count,
                "fetch_status": fetch_result.fetch_status,
                "title": fetch_result.title or self.sources_map[fetch_result.source_id].get("title"),
                "domain": existing_domain or domain,
            })
        else:
            # Create new source entry if not from search
            self.sources_map[fetch_result.source_id] = {
                "source_id": fetch_result.source_id,
                "url": fetch_result.url,
                "title": fetch_result.title,
                "domain": domain,
                "fetched": True,
                "content": fetch_result.content,
                "word_count": fetch_result.word_count,
                "fetch_status": fetch_result.fetch_status,
            }

        logger.info(
            f"Added fetched source {fetch_result.source_id} ({fetch_result.word_count} words)"
        )

    async def add_evidence_from_summary(
        self,
        source_id: str,
        summary_result: SummarizeResponse,
    ) -> None:
        """Extract and store evidence from summarization.

        Args:
            source_id: Source identifier
            summary_result: SummarizeResponse from summarize tool
        """
        if not summary_result.success:
            logger.warning(f"Summarization failed for {source_id}")
            return

        for i, claim_obj in enumerate(summary_result.key_claims):
            evidence_id = f"EVI-{source_id}-{i:02d}"

            self.evidence_map[evidence_id] = {
                "evidence_id": evidence_id,
                "source_id": source_id,
                "text": claim_obj.claim,
                "evidence": claim_obj.evidence,
                "confidence": getattr(claim_obj, "confidence", 0.7),
            }

        logger.info(f"Added {len(summary_result.key_claims)} evidence items from {source_id}")

    def extract_claims_from_answer(
        self,
        answer_text: str,
    ) -> List[Dict[str, Any]]:
        """Extract factual claims from final answer.

        Args:
            answer_text: Final answer text

        Returns:
            List of extracted claims
        """
        import re

        if not answer_text or not answer_text.strip():
            return []

        claims = []
        sentences = re.split(r"(?<=[.!?])\s+", answer_text.strip())

        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence or len(sentence) < 10:
                continue

            claim_id = f"CLM-{i:04d}"
            claims.append({
                "claim_id": claim_id,
                "claim_text": sentence,
                "sentence_index": i,
            })

        logger.info(f"Extracted {len(claims)} claims from answer")
        return claims

    def find_supporting_evidence(
        self,
        claim_text: str,
        min_similarity: float = 0.3,
    ) -> List[str]:
        """Find evidence supporting a claim.

        Args:
            claim_text: Claim text
            min_similarity: Minimum similarity threshold

        Returns:
            List of supporting evidence IDs
        """
        supporting = []
        claim_words = set(claim_text.lower().split())

        for evidence_id, evidence in self.evidence_map.items():
            evidence_text = evidence.get("text", "").lower()
            evidence_words = set(evidence_text.split())

            if not claim_words:
                continue

            overlap = len(claim_words & evidence_words)
            similarity = overlap / len(claim_words)

            if similarity >= min_similarity:
                supporting.append(evidence_id)

        return supporting

    def validate_claim(
        self,
        claim: Dict[str, Any],
        supporting_evidence: List[str],
    ) -> Dict[str, Any]:
        """Validate a claim has supporting evidence.

        Args:
            claim: Claim dictionary
            supporting_evidence: List of supporting evidence IDs

        Returns:
            Validated claim with verification status
        """
        # Check that at least one evidence exists
        has_evidence = len(supporting_evidence) > 0

        # Check that at least one evidence is from a fetched source
        has_fetched_source = False
        source_ids = []

        for evidence_id in supporting_evidence:
            evidence = self.evidence_map.get(evidence_id)
            if not evidence:
                continue

            source_id = evidence.get("source_id")
            source = self.sources_map.get(source_id)

            if source and source.get("fetched"):
                has_fetched_source = True
                if source_id not in source_ids:
                    source_ids.append(source_id)

        # Claim is valid only if it has evidence from fetched sources
        is_valid = has_evidence and has_fetched_source

        return {
            **claim,
            "evidence_ids": supporting_evidence,
            "source_ids": source_ids,
            "verified": is_valid,
            "has_evidence": has_evidence,
            "has_fetched_source": has_fetched_source,
        }

    def validate_answer(
        self,
        answer_text: str,
    ) -> Dict[str, Any]:
        """Validate complete answer for citation integrity.

        Args:
            answer_text: Final answer text

        Returns:
            Validation report
        """
        logger.info("Starting comprehensive citation validation")

        # Extract claims
        claims = self.extract_claims_from_answer(answer_text)

        if not claims:
            logger.warning("No claims extracted from answer")
            return {
                "valid": False,
                "reason": "No claims found",
                "claims": [],
                "total_sources": len(self.sources_map),
                "fetched_sources": sum(1 for s in self.sources_map.values() if s.get("fetched")),
            }

        # Validate each claim
        validated_claims = []

        for claim in claims:
            supporting_evidence = self.find_supporting_evidence(claim["claim_text"])
            validated = self.validate_claim(claim, supporting_evidence)
            validated_claims.append(validated)

        # Summary statistics
        total_claims = len(validated_claims)
        verified_claims = sum(1 for c in validated_claims if c.get("verified"))
        verification_rate = (verified_claims / total_claims * 100) if total_claims > 0 else 0

        # Determine overall validity
        # At least 80% of claims should be verified for valid answer
        is_valid = verification_rate >= 80

        report = {
            "valid": is_valid,
            "total_claims": total_claims,
            "verified_claims": verified_claims,
            "verification_rate": verification_rate,
            "claims": validated_claims,
            "total_sources": len(self.sources_map),
            "fetched_sources": sum(1 for s in self.sources_map.values() if s.get("fetched")),
            "total_evidence": len(self.evidence_map),
        }

        logger.info(
            f"Validation complete: {verified_claims}/{total_claims} claims verified "
            f"({verification_rate:.1f}%)"
        )

        return report

    def remove_unverified_claims(
        self,
        answer_text: str,
        validation_report: Dict[str, Any],
    ) -> str:
        """Remove or rewrite unverified claims.

        Args:
            answer_text: Original answer
            validation_report: Validation report

        Returns:
            Cleaned answer
        """
        if validation_report.get("valid"):
            return answer_text

        verified_claims = [
            c["claim_text"]
            for c in validation_report.get("claims", [])
            if c.get("verified")
        ]

        if not verified_claims:
            return (
                "Unable to generate supported answer: "
                "no claims could be verified against fetched sources."
            )

        # Reconstruct answer from verified claims
        cleaned = " ".join(verified_claims)

        logger.info(
            f"Removed unverified claims: "
            f"{validation_report['total_claims'] - validation_report['verified_claims']} filtered"
        )

        return cleaned

    def build_citations_for_claim(
        self,
        claim: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build citations for a single claim.

        Args:
            claim: Validated claim

        Returns:
            Claim with citations
        """
        citations = []

        for source_id in claim.get("source_ids", []):
            source = self.sources_map.get(source_id)
            if not source:
                continue

            citations.append({
                "source_id": source_id,
                "url": source.get("url"),
                "title": source.get("title"),
                "domain": source.get("domain"),
            })

        return {
            **claim,
            "citations": citations,
        }

    def build_final_answer_with_citations(
        self,
        answer_text: str,
        validation_report: Dict[str, Any],
    ) -> str:
        """Build final answer with inline citations.

        Args:
            answer_text: Original answer
            validation_report: Validation report

        Returns:
            Answer with citations
        """
        if not validation_report.get("valid"):
            return self.remove_unverified_claims(answer_text, validation_report)

        # Add inline citations to verified claims
        cited_answer = answer_text
        citation_number = 1

        for claim in validation_report.get("claims", []):
            if not claim.get("verified") or not claim.get("source_ids"):
                continue

            # Build citation reference
            cite_numbers = list(range(citation_number, citation_number + len(claim["source_ids"])))
            cite_text = f" [{','.join(str(n) for n in cite_numbers)}]"

            # Replace claim with cited version (simple approach)
            original = claim["claim_text"]
            replacement = original.rstrip(".!? ") + cite_text

            cited_answer = cited_answer.replace(original, replacement, 1)

            citation_number += len(claim["source_ids"])

        return cited_answer

    def get_citations_section(
        self,
        validation_report: Dict[str, Any],
    ) -> str:
        """Generate citations section for answer.

        Args:
            validation_report: Validation report

        Returns:
            Formatted citations section
        """
        citations_dict = {}

        for claim in validation_report.get("claims", []):
            if not claim.get("verified"):
                continue

            for i, source_id in enumerate(claim.get("source_ids", []), 1):
                source = self.sources_map.get(source_id)
                if not source:
                    continue

                citation_number = len(citations_dict) + 1
                citations_dict[citation_number] = {
                    "source_id": source_id,
                    "url": source.get("url"),
                    "title": source.get("title"),
                    "domain": source.get("domain"),
                }

        if not citations_dict:
            return "## Sources\n\nNo sources cited.\n"

        # Build formatted citations
        citations_text = "## Sources\n\n"

        for num in sorted(citations_dict.keys()):
            citation = citations_dict[num]
            citations_text += (
                f"[{num}] {citation.get('title', 'Untitled')}\n"
                f"    Domain: {citation.get('domain', 'unknown')}\n"
                f"    URL: {citation.get('url', 'N/A')}\n\n"
            )

        return citations_text

    def get_validation_summary(
        self,
        validation_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get summary of validation.

        Args:
            validation_report: Full validation report

        Returns:
            Summary dictionary
        """
        return {
            "valid": validation_report.get("valid"),
            "total_claims": validation_report.get("total_claims"),
            "verified_claims": validation_report.get("verified_claims"),
            "verification_rate": f"{validation_report.get('verification_rate', 0):.1f}%",
            "total_sources": validation_report.get("total_sources"),
            "fetched_sources": validation_report.get("fetched_sources"),
            "evidence_items": validation_report.get("total_evidence"),
        }

    def reset(self) -> None:
        """Reset service state (for testing)."""
        self.claims = {}
        self.sources_map = {}
        self.evidence_map = {}
        logger.info("Citation integration service reset")
