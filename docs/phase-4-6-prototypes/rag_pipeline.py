"""
RAG (Retrieval-Augmented Generation) Pipeline for Evidence Extraction.

This module provides the core RAG functionality:
- Content chunking and processing
- Evidence extraction from fetched pages
- Evidence-to-source mapping
- Retrieval and evidence synthesis
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """Individual piece of evidence extracted from a source."""

    evidence_id: str  # EVI-001, EVI-002, etc.
    source_id: str
    text: str
    confidence: float = 1.0  # 0.0 to 1.0
    chunk_index: int = 0
    is_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Claim:
    """A factual claim that needs evidence."""

    claim_id: str  # CLM-001, CLM-002, etc.
    text: str
    research_run_id: Optional[int] = None
    evidence_ids: List[str] = field(default_factory=list)
    has_source: bool = False
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class SourceEvidence:
    """Complete evidence structure for a source."""

    source_id: str
    url: str
    title: Optional[str]
    domain: Optional[str]
    fetched_content: str
    evidence_list: List[Evidence] = field(default_factory=list)
    word_count: int = 0
    processing_status: str = "pending"  # pending, chunked, extracted, indexed
    raw_chunks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "domain": self.domain,
            "word_count": self.word_count,
            "processing_status": self.processing_status,
            "evidence_count": len(self.evidence_list),
            "evidence": [e.to_dict() for e in self.evidence_list],
        }


class ContentChunker:
    """Chunks content into logically coherent segments."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        """Initialize chunker.

        Args:
            chunk_size: Target words per chunk
            overlap: Words to overlap between chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_by_paragraphs(self, content: str) -> List[str]:
        """Chunk content by paragraphs (preferred method).

        Args:
            content: Raw content to chunk

        Returns:
            List of chunks
        """
        if not content or not content.strip():
            return []

        # Split by double newlines (paragraphs)
        paragraphs = re.split(r"\n\n+", content.strip())

        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            # Remove excessive whitespace within paragraph
            para = " ".join(para.split())

            if not para:
                continue

            # If current chunk is empty, start with this paragraph
            if not current_chunk:
                current_chunk = para
                continue

            # Check if adding this paragraph would exceed chunk_size
            combined = current_chunk + "\n\n" + para
            word_count = len(combined.split())

            if word_count <= self.chunk_size:
                current_chunk = combined
            else:
                # Save current chunk and start new one
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def chunk_by_sentences(self, content: str) -> List[str]:
        """Chunk content by sentences (fallback method).

        Args:
            content: Raw content to chunk

        Returns:
            List of chunks
        """
        if not content or not content.strip():
            return []

        # Split by sentence delimiters
        sentences = re.split(r"(?<=[.!?])\s+", content.strip())

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if not current_chunk:
                current_chunk = sentence
                continue

            combined = current_chunk + " " + sentence
            word_count = len(combined.split())

            if word_count <= self.chunk_size:
                current_chunk = combined
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def chunk(self, content: str) -> List[str]:
        """Chunk content, preferring paragraph-based chunking.

        Args:
            content: Raw content to chunk

        Returns:
            List of chunks
        """
        # Try paragraph-based chunking first
        chunks = self.chunk_by_paragraphs(content)

        # If no chunks from paragraphs (no double newlines), try sentences
        if not chunks:
            chunks = self.chunk_by_sentences(content)

        # If still no chunks, split into words manually
        if not chunks and content.strip():
            words = content.split()
            for i in range(0, len(words), self.chunk_size):
                chunk = " ".join(words[i : i + self.chunk_size])
                if chunk.strip():
                    chunks.append(chunk)

        return chunks


class EvidenceExtractor:
    """Extracts evidence from chunked content."""

    def __init__(self):
        """Initialize extractor."""
        self.evidence_counter = 0
        # Patterns that indicate evidence-bearing text
        self.evidence_patterns = [
            r"(according to|research shows|studies|evidence|found|demonstrated|proved|significant|result|data|analysis)",
        ]

    def extract_evidence(
        self, source_id: str, chunks: List[str]
    ) -> List[Evidence]:
        """Extract evidence from chunks.

        Args:
            source_id: Source identifier
            chunks: List of content chunks

        Returns:
            List of Evidence objects
        """
        evidence_list: List[Evidence] = []

        for chunk_idx, chunk in enumerate(chunks):
            if not chunk or not chunk.strip():
                continue

            # All chunks are potentially evidence
            # Confidence based on presence of evidence indicators
            confidence = self._calculate_confidence(chunk)

            evidence_id = f"EVI-{self.evidence_counter:04d}"
            self.evidence_counter += 1

            evidence = Evidence(
                evidence_id=evidence_id,
                source_id=source_id,
                text=chunk.strip(),
                confidence=confidence,
                chunk_index=chunk_idx,
                is_verified=False,
            )

            evidence_list.append(evidence)
            logger.debug(
                f"Extracted {evidence_id} from {source_id}, confidence={confidence:.2f}"
            )

        return evidence_list

    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score for evidence.

        Args:
            text: Text to evaluate

        Returns:
            Confidence score (0.0-1.0)
        """
        if not text or not text.strip():
            return 0.0

        confidence = 0.5  # Base confidence

        # Increase confidence if text contains evidence indicators
        for pattern in self.evidence_patterns:
            if re.search(pattern, text.lower()):
                confidence = min(1.0, confidence + 0.2)
                break

        # Increase confidence with text length (more content = more evidence)
        word_count = len(text.split())
        if word_count > 100:
            confidence = min(1.0, confidence + 0.15)
        elif word_count > 50:
            confidence = min(1.0, confidence + 0.05)

        return confidence


class RAGPipeline:
    """Complete RAG pipeline for processing sources into evidence."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        """Initialize RAG pipeline.

        Args:
            chunk_size: Words per chunk
            overlap: Word overlap between chunks
        """
        self.chunker = ContentChunker(chunk_size=chunk_size, overlap=overlap)
        self.extractor = EvidenceExtractor()
        self.processed_sources: Dict[str, SourceEvidence] = {}

    def process_source(
        self,
        source_id: str,
        url: str,
        content: str,
        title: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> SourceEvidence:
        """Process a source through the complete RAG pipeline.

        Args:
            source_id: Source identifier (SRC-001, etc.)
            url: Source URL
            content: Full fetched content
            title: Source title
            domain: Source domain

        Returns:
            SourceEvidence with chunks and evidence
        """
        logger.info(f"Starting RAG processing for {source_id}")

        source_evidence = SourceEvidence(
            source_id=source_id,
            url=url,
            title=title,
            domain=domain,
            fetched_content=content,
            word_count=len(content.split()) if content else 0,
            processing_status="pending",
        )

        if not content or not content.strip():
            logger.warning(f"Empty content for {source_id}")
            source_evidence.processing_status = "error"
            return source_evidence

        # Step 1: Chunk content
        try:
            chunks = self.chunker.chunk(content)
            source_evidence.raw_chunks = chunks
            source_evidence.processing_status = "chunked"
            logger.info(f"Chunked {source_id} into {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Chunking failed for {source_id}: {e}")
            source_evidence.processing_status = "error"
            return source_evidence

        # Step 2: Extract evidence
        try:
            evidence_list = self.extractor.extract_evidence(source_id, chunks)
            source_evidence.evidence_list = evidence_list
            source_evidence.processing_status = "extracted"
            logger.info(f"Extracted {len(evidence_list)} evidence items from {source_id}")
        except Exception as e:
            logger.error(f"Evidence extraction failed for {source_id}: {e}")
            source_evidence.processing_status = "error"
            return source_evidence

        # Store processed source
        self.processed_sources[source_id] = source_evidence
        source_evidence.processing_status = "indexed"

        logger.info(
            f"Completed RAG processing for {source_id}: "
            f"chunks={len(chunks)}, evidence={len(evidence_list)}"
        )

        return source_evidence

    def get_source_evidence(self, source_id: str) -> Optional[SourceEvidence]:
        """Retrieve processed source evidence.

        Args:
            source_id: Source identifier

        Returns:
            SourceEvidence or None
        """
        return self.processed_sources.get(source_id)

    def search_evidence(
        self, query: str, source_id: Optional[str] = None
    ) -> List[Evidence]:
        """Search evidence by keyword.

        Args:
            query: Search query
            source_id: Optional source to limit search

        Returns:
            Matching evidence items
        """
        results: List[Evidence] = []
        query_lower = query.lower()

        sources = (
            [self.processed_sources[source_id]]
            if source_id and source_id in self.processed_sources
            else self.processed_sources.values()
        )

        for source_evidence in sources:
            for evidence in source_evidence.evidence_list:
                if query_lower in evidence.text.lower():
                    results.append(evidence)

        return results

    def get_all_evidence(self) -> List[Evidence]:
        """Get all extracted evidence.

        Returns:
            All evidence items
        """
        all_evidence: List[Evidence] = []
        for source_evidence in self.processed_sources.values():
            all_evidence.extend(source_evidence.evidence_list)
        return all_evidence

    def get_processed_sources_summary(self) -> Dict[str, Any]:
        """Get summary of all processed sources.

        Returns:
            Summary dictionary
        """
        return {
            "total_sources": len(self.processed_sources),
            "total_evidence": sum(
                len(s.evidence_list) for s in self.processed_sources.values()
            ),
            "sources": {
                src_id: src.to_dict()
                for src_id, src in self.processed_sources.items()
            },
        }
