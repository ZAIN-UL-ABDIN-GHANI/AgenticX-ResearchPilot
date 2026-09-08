"""
Citation Validator - Ensures every claim has traceable source evidence.

Core principle: NO SOURCE = NO CLAIM

Implements:
- Claim extraction from final answer
- Evidence verification
- Citation link validation
- Source traceability checking
- Claim-Evidence-Source chain building
"""

import logging
import re
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class VerifiableClaim:
    """A claim that requires verification."""

    claim_id: str
    claim_text: str
    evidence_ids: List[str]
    source_ids: List[str]
    verified: bool
    is_traceable: bool
    confidence: float


@dataclass
class CitationLink:
    """A link from claim to source."""

    claim_id: str
    source_id: str
    evidence_text: str
    citation_number: int
    verified: bool


@dataclass
class TraceabilityChain:
    """Complete traceability chain for a claim."""

    claim_id: str
    claim_text: str
    evidence_ids: List[str]
    source_ids: List[str]
    chain_steps: List[Dict[str, Any]]  # Claim → Evidence → Source
    is_complete: bool
    is_valid: bool


class ClaimExtractor:
    """Extracts factual claims from text."""

    def __init__(self):
        """Initialize claim extractor."""
        self.claim_counter = 0

    def extract_claims(self, text: str) -> List[Tuple[str, str]]:
        """Extract claims from text.

        Args:
            text: Text to extract claims from

        Returns:
            List of (claim_id, claim_text) tuples
        """
        if not text or not text.strip():
            return []

        claims = []

        # Split by sentence
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence or len(sentence) < 10:
                continue

            # Filter out meta-text
            if self._is_meta_text(sentence):
                continue

            # Create claim
            claim_id = f"CLM-{self.claim_counter:04d}"
            self.claim_counter += 1

            claims.append((claim_id, sentence))

        logger.info(f"Extracted {len(claims)} claims from text")
        return claims

    def _is_meta_text(self, text: str) -> bool:
        """Check if text is meta (not a factual claim).

        Args:
            text: Text to check

        Returns:
            True if meta text
        """
        meta_patterns = [
            r"^(research|study|article|paper|document|source).*:",
            r"^(step|phase|section|chapter)",
            r"^(note|disclaimer|warning)",
            r"^(error|failed|unable to)",
        ]

        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in meta_patterns)


class EvidenceVerifier:
    """Verifies evidence supports claims."""

    @staticmethod
    def find_supporting_evidence(
        claim_text: str,
        evidence_list: List[Dict[str, Any]],
        similarity_threshold: float = 0.5,
    ) -> List[str]:
        """Find evidence supporting a claim.

        Args:
            claim_text: Claim text
            evidence_list: List of available evidence
            similarity_threshold: Minimum similarity score

        Returns:
            List of supporting evidence IDs
        """
        supporting = []

        for evidence in evidence_list:
            evidence_text = evidence.get("text", "").lower()
            claim_lower = claim_text.lower()

            # Simple keyword matching
            claim_words = set(claim_lower.split())
            evidence_words = set(evidence_text.split())

            overlap = len(claim_words & evidence_words)
            if claim_words:
                similarity = overlap / len(claim_words)
            else:
                similarity = 0.0

            if similarity >= similarity_threshold:
                supporting.append(evidence.get("evidence_id"))

        return supporting

    @staticmethod
    def verify_evidence_in_source(
        evidence_text: str,
        source_content: str,
    ) -> bool:
        """Verify evidence text exists in source.

        Args:
            evidence_text: Evidence text to verify
            source_content: Source content

        Returns:
            True if evidence found in source
        """
        if not evidence_text or not source_content:
            return False

        # Check for exact match
        if evidence_text in source_content:
            return True

        # Check for substring match (with some tolerance)
        evidence_normalized = " ".join(evidence_text.split())
        content_normalized = " ".join(source_content.split())

        if evidence_normalized in content_normalized:
            return True

        # Check for keyword match (at least 70% of words match)
        evidence_words = set(evidence_normalized.split())
        content_words = set(content_normalized.split())

        if evidence_words:
            overlap = len(evidence_words & content_words)
            similarity = overlap / len(evidence_words)
            return similarity >= 0.7

        return False


class CitationBuilder:
    """Builds citations for verified claims."""

    @staticmethod
    def build_citations_for_claims(
        claims: List[Dict[str, Any]],
        evidence_map: Dict[str, Dict[str, Any]],
        source_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, CitationLink]:
        """Build citations for all claims.

        Args:
            claims: List of verified claims
            evidence_map: Mapping of evidence_id -> evidence
            source_map: Mapping of source_id -> source

        Returns:
            Dictionary of citation_links
        """
        citations = {}
        citation_number = 1

        for claim in claims:
            if not claim.get("verified"):
                continue

            source_ids = claim.get("source_ids", [])
            if not source_ids:
                continue

            for source_id in source_ids:
                link_key = f"{claim['claim_id']}_{source_id}"

                link = CitationLink(
                    claim_id=claim["claim_id"],
                    source_id=source_id,
                    evidence_text=claim.get("claim_text", ""),
                    citation_number=citation_number,
                    verified=True,
                )

                citations[link_key] = link
                citation_number += 1

        return citations

    @staticmethod
    def generate_citation_text(
        citation_links: Dict[str, CitationLink],
    ) -> Dict[str, str]:
        """Generate citation text references.

        Args:
            citation_links: Links from builder

        Returns:
            Citation text mapping
        """
        citations = {}

        for link in citation_links.values():
            citation_ref = f"[{link.citation_number}]"
            source_info = f"Source: {link.source_id}"

            citations[citation_ref] = source_info

        return citations


class TraceabilityValidator:
    """Validates complete claim→evidence→source traceability."""

    @staticmethod
    def build_traceability_chain(
        claim_id: str,
        claim_text: str,
        evidence_ids: List[str],
        source_ids: List[str],
        evidence_map: Dict[str, Dict[str, Any]],
        source_map: Dict[str, Dict[str, Any]],
    ) -> TraceabilityChain:
        """Build and validate traceability chain.

        Args:
            claim_id: Claim identifier
            claim_text: Claim text
            evidence_ids: Supporting evidence IDs
            source_ids: Supporting source IDs
            evidence_map: Evidence mapping
            source_map: Source mapping

        Returns:
            TraceabilityChain object
        """
        chain_steps = []
        is_complete = True
        is_valid = True

        # Step 1: Claim
        chain_steps.append({
            "step": 1,
            "type": "claim",
            "id": claim_id,
            "text": claim_text,
            "valid": True,
        })

        # Step 2: Evidence
        for evidence_id in evidence_ids:
            evidence = evidence_map.get(evidence_id)

            if not evidence:
                chain_steps.append({
                    "step": 2,
                    "type": "evidence",
                    "id": evidence_id,
                    "text": "NOT FOUND",
                    "valid": False,
                })
                is_valid = False
                is_complete = False
                continue

            chain_steps.append({
                "step": 2,
                "type": "evidence",
                "id": evidence_id,
                "text": evidence.get("text", ""),
                "confidence": evidence.get("confidence", 0),
                "valid": True,
            })

        # Step 3: Source
        for source_id in source_ids:
            source = source_map.get(source_id)

            if not source:
                chain_steps.append({
                    "step": 3,
                    "type": "source",
                    "id": source_id,
                    "url": "NOT FOUND",
                    "valid": False,
                })
                is_valid = False
                is_complete = False
                continue

            # Check if source was actually fetched
            is_fetched = source.get("fetched", False)

            chain_steps.append({
                "step": 3,
                "type": "source",
                "id": source_id,
                "url": source.get("url", ""),
                "title": source.get("title", ""),
                "fetched": is_fetched,
                "valid": is_fetched,
            })

            if not is_fetched:
                is_valid = False

        return TraceabilityChain(
            claim_id=claim_id,
            claim_text=claim_text,
            evidence_ids=evidence_ids,
            source_ids=source_ids,
            chain_steps=chain_steps,
            is_complete=is_complete,
            is_valid=is_valid,
        )

    @staticmethod
    def validate_chain(chain: TraceabilityChain) -> bool:
        """Validate a traceability chain.

        Args:
            chain: TraceabilityChain to validate

        Returns:
            True if chain is valid
        """
        if not chain.is_complete:
            logger.warning(f"Chain {chain.claim_id} is incomplete")
            return False

        if not chain.is_valid:
            logger.warning(f"Chain {chain.claim_id} is invalid")
            return False

        # All steps must have valid=True
        for step in chain.chain_steps:
            if not step.get("valid", False):
                logger.warning(
                    f"Chain {chain.claim_id} has invalid step: {step['type']}"
                )
                return False

        return True

    @staticmethod
    def build_all_chains(
        claims: List[Dict[str, Any]],
        evidence_map: Dict[str, Dict[str, Any]],
        source_map: Dict[str, Dict[str, Any]],
    ) -> List[TraceabilityChain]:
        """Build traceability chains for all claims.

        Args:
            claims: List of claims
            evidence_map: Evidence mapping
            source_map: Source mapping

        Returns:
            List of TraceabilityChain objects
        """
        chains = []

        for claim in claims:
            chain = TraceabilityValidator.build_traceability_chain(
                claim_id=claim.get("claim_id"),
                claim_text=claim.get("claim_text", ""),
                evidence_ids=claim.get("evidence_ids", []),
                source_ids=claim.get("source_ids", []),
                evidence_map=evidence_map,
                source_map=source_map,
            )

            chains.append(chain)

        return chains


class CitationValidator:
    """Main citation validation orchestrator."""

    def __init__(self):
        """Initialize validator."""
        self.claim_extractor = ClaimExtractor()
        self.evidence_verifier = EvidenceVerifier()
        self.citation_builder = CitationBuilder()
        self.traceability_validator = TraceabilityValidator()

    def validate_answer(
        self,
        answer_text: str,
        evidence_list: List[Dict[str, Any]],
        source_list: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Validate complete answer for citation integrity.

        Args:
            answer_text: Final answer text
            evidence_list: List of available evidence
            source_list: List of available sources

        Returns:
            Validation report
        """
        logger.info("Starting citation validation")

        # Extract claims
        extracted_claims = self.claim_extractor.extract_claims(answer_text)

        if not extracted_claims:
            logger.warning("No claims extracted from answer")
            return {
                "valid": False,
                "reason": "No claims found in answer",
                "claims": [],
                "evidence_count": len(evidence_list),
                "source_count": len(source_list),
            }

        # Build maps
        evidence_map = {e.get("evidence_id"): e for e in evidence_list}
        source_map = {s.get("source_id"): s for s in source_list}

        # Verify each claim
        verified_claims = []

        for claim_id, claim_text in extracted_claims:
            # Find supporting evidence
            supporting_evidence = self.evidence_verifier.find_supporting_evidence(
                claim_text, evidence_list, similarity_threshold=0.3
            )

            # Find sources for evidence
            supporting_sources = []
            for evidence_id in supporting_evidence:
                evidence = evidence_map.get(evidence_id)
                if evidence:
                    source_id = evidence.get("source_id")
                    if source_id and source_id not in supporting_sources:
                        supporting_sources.append(source_id)

            # Verify at least one source
            has_source = len(supporting_sources) > 0
            is_traceable = len(supporting_evidence) > 0 and has_source

            verified_claim = {
                "claim_id": claim_id,
                "claim_text": claim_text,
                "evidence_ids": supporting_evidence,
                "source_ids": supporting_sources,
                "verified": is_traceable,
                "is_traceable": is_traceable,
                "confidence": min(1.0, len(supporting_sources) * 0.5),
            }

            verified_claims.append(verified_claim)

        # Build traceability chains
        chains = self.traceability_validator.build_all_chains(
            verified_claims, evidence_map, source_map
        )

        # Build citations
        citations = self.citation_builder.build_citations_for_claims(
            verified_claims, evidence_map, source_map
        )

        # Validate chains
        valid_chains = sum(
            1 for chain in chains
            if self.traceability_validator.validate_chain(chain)
        )

        # Final determination
        total_claims = len(verified_claims)
        traceable_claims = sum(1 for c in verified_claims if c["verified"])

        is_valid = traceable_claims > 0 and traceable_claims >= total_claims * 0.8

        report = {
            "valid": is_valid,
            "total_claims": total_claims,
            "verified_claims": traceable_claims,
            "traceability_percentage": (
                (traceable_claims / total_claims * 100) if total_claims > 0 else 0
            ),
            "valid_chains": valid_chains,
            "claims": verified_claims,
            "chains": [
                {
                    "claim_id": chain.claim_id,
                    "valid": self.traceability_validator.validate_chain(chain),
                    "steps": chain.chain_steps,
                }
                for chain in chains
            ],
            "citations": citations,
        }

        logger.info(
            f"Validation complete: {traceable_claims}/{total_claims} claims verified"
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
            Cleaned answer with only verified claims
        """
        if validation_report.get("valid"):
            return answer_text

        verified_claims = {
            c["claim_text"]
            for c in validation_report.get("claims", [])
            if c.get("verified")
        }

        if not verified_claims:
            return "Unable to generate answer: no verifiable claims found."

        # Keep only verified claims
        sentences = re.split(r"(?<=[.!?])\s+", answer_text.strip())
        verified_sentences = [
            s for s in sentences
            if any(claim[:20] in s for claim in verified_claims)
        ]

        if not verified_sentences:
            return "Answer contains no verifiable claims based on collected evidence."

        return " ".join(verified_sentences)

    def get_validation_summary(
        self, validation_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get summary of validation.

        Args:
            validation_report: Full validation report

        Returns:
            Summary dict
        """
        return {
            "valid": validation_report.get("valid"),
            "total_claims": validation_report.get("total_claims"),
            "verified_claims": validation_report.get("verified_claims"),
            "traceability_percentage": validation_report.get(
                "traceability_percentage"
            ),
            "citation_count": len(validation_report.get("citations", {})),
        }
