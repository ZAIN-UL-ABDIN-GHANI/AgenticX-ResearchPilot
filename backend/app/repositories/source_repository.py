"""
Repository for sources table operations.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Source
from app.core.logging import get_logger

logger = get_logger(__name__)


class SourceRepository:
    """Repository for source data access."""
    
    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session
    
    async def create(
        self,
        research_run_id: int,
        source_id: str,
        url: str,
        title: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> Source:
        """Create a new source."""
        source = Source(
            research_run_id=research_run_id,
            source_id=source_id,
            url=url,
            title=title,
            domain=domain,
        )
        self.session.add(source)
        await self.session.flush()
        logger.info(f"Created source {source_id}: {url}")
        return source
    
    async def get(self, source_id: int) -> Optional[Source]:
        """Get source by ID."""
        result = await self.session.execute(
            select(Source).where(Source.id == source_id)
        )
        return result.scalars().first()
    
    async def get_by_source_id(self, research_run_id: int, source_id: str) -> Optional[Source]:
        """Get a source by its human-readable source_id, scoped to one
        research run.

        source_id values (e.g. "SRC-001") are only unique *within* a single
        research run, not across the whole `sources` table -- every run
        starts renumbering from SRC-001. Looking this up without also
        filtering by research_run_id would risk matching a different run's
        source entirely and misattributing a citation to unrelated content.
        """
        result = await self.session.execute(
            select(Source).where(
                Source.research_run_id == research_run_id,
                Source.source_id == source_id,
            )
        )
        return result.scalars().first()
    
    async def get_by_research(self, research_run_id: int) -> List[Source]:
        """Get all sources for a research run."""
        result = await self.session.execute(
            select(Source).where(Source.research_run_id == research_run_id)
        )
        return result.scalars().all()
    
    async def update(self, source_id: int, **kwargs) -> Optional[Source]:
        """Update source."""
        await self.session.execute(
            update(Source)
            .where(Source.id == source_id)
            .values(**kwargs)
        )
        await self.session.flush()
        return await self.get(source_id)
    
    async def mark_fetched(
        self,
        source_id: int,
        content: str,
        word_count: int,
    ) -> Optional[Source]:
        """Mark source as fetched."""
        return await self.update(
            source_id,
            fetch_status="success",
            content=content,
            word_count=word_count,
            fetched_at=datetime.utcnow(),
        )
    
    async def mark_fetch_error(self, source_id: int, error: str) -> Optional[Source]:
        """Mark source fetch as failed."""
        return await self.update(
            source_id,
            fetch_status="error",
            fetched_at=datetime.utcnow(),
        )
    
    async def delete(self, source_id: int) -> bool:
        """Delete source."""
        source = await self.get(source_id)
        if source:
            await self.session.delete(source)
            await self.session.flush()
            return True
        return False
