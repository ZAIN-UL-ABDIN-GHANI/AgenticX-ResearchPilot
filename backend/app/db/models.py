"""
SQLAlchemy ORM models for ResearchPilot AI.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, JSON, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class ResearchRun(Base, TimestampMixin):
    """Research run model."""
    
    __tablename__ = "research_runs"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String(500), nullable=False)
    status = Column(String(50), default="running", index=True)  # running, completed, failed
    max_steps = Column(Integer, default=8)
    steps_used = Column(Integer, default=0)
    final_answer = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    sources = relationship("Source", back_populates="research_run", cascade="all, delete-orphan")
    tool_calls = relationship("ToolCall", back_populates="research_run", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="research_run", cascade="all, delete-orphan")


class Source(Base, TimestampMixin):
    """Source/evidence model."""
    
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("research_run_id", "source_id", name="uq_research_source"),
        Index("idx_sources_research_run_id", "research_run_id"),
        Index("idx_fetch_status", "fetch_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    research_run_id = Column(Integer, ForeignKey("research_runs.id"), nullable=False)
    source_id = Column(String(50), nullable=False)  # SRC-001, etc.
    url = Column(String(2000), nullable=False)
    title = Column(String(500), nullable=True)
    domain = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    fetch_status = Column(String(50), default="pending")  # pending, success, timeout, error, forbidden
    fetched_at = Column(DateTime, nullable=True)
    word_count = Column(Integer, nullable=True)

    # Relationships
    research_run = relationship("ResearchRun", back_populates="sources")
    claim_sources = relationship("ClaimSource", back_populates="source")


class ToolCall(Base, TimestampMixin):
    """Tool call record model."""
    
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("idx_tool_calls_research_run_id", "research_run_id"),
        Index("idx_tool_name", "tool_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    research_run_id = Column(Integer, ForeignKey("research_runs.id"), nullable=False)
    tool_name = Column(String(100), nullable=False)  # web_search, fetch_page, summarize
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    status = Column(String(50), default="success")  # success, error, timeout
    step_number = Column(Integer, nullable=True)

    # Relationships
    research_run = relationship("ResearchRun", back_populates="tool_calls")


class Claim(Base, TimestampMixin):
    """Claim model for evidence tracking."""
    
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    research_run_id = Column(Integer, ForeignKey("research_runs.id"), nullable=False)
    claim_text = Column(Text, nullable=False)

    # Relationships
    research_run = relationship("ResearchRun", back_populates="claims")
    claim_sources = relationship("ClaimSource", back_populates="claim")


class ClaimSource(Base):
    """Junction table linking claims to sources."""
    
    __tablename__ = "claim_sources"

    claim_id = Column(Integer, ForeignKey("claims.id"), primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id"), primary_key=True)
    evidence = Column(Text, nullable=True)
    citation_number = Column(Integer, nullable=True)
    confidence = Column(Integer, nullable=True)  # 0-100

    # Relationships
    claim = relationship("Claim", back_populates="claim_sources")
    source = relationship("Source", back_populates="claim_sources")
