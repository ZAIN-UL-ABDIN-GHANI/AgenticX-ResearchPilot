"""
Repository for research_runs table operations.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ResearchRun
from app.core.logging import get_logger

logger = get_logger(__name__)


class ResearchRepository:
    """Repository for research run data access."""
    
    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session
    
    async def create(self, question: str, max_steps: int = 8) -> ResearchRun:
        """Create a new research run."""
        research = ResearchRun(question=question, max_steps=max_steps)
        self.session.add(research)
        await self.session.flush()
        logger.info(f"Created research run {research.id}: {question}")
        return research
    
    async def get(self, research_id: int) -> Optional[ResearchRun]:
        """Get research by ID."""
        result = await self.session.execute(
            select(ResearchRun).where(ResearchRun.id == research_id)
        )
        return result.scalars().first()
    
    async def get_all(self, limit: int = 100) -> List[ResearchRun]:
        """Get all research runs."""
        result = await self.session.execute(
            select(ResearchRun).limit(limit)
        )
        return result.scalars().all()
    
    async def update(self, research_id: int, **kwargs) -> Optional[ResearchRun]:
        """Update research run."""
        await self.session.execute(
            update(ResearchRun)
            .where(ResearchRun.id == research_id)
            .values(**kwargs)
        )
        await self.session.flush()
        return await self.get(research_id)
    
    async def complete(self, research_id: int, final_answer: str) -> Optional[ResearchRun]:
        """Mark research as completed."""
        return await self.update(
            research_id,
            status="completed",
            final_answer=final_answer,
            completed_at=datetime.utcnow(),
        )
    
    async def fail(self, research_id: int, error: str = "") -> Optional[ResearchRun]:
        """Mark research as failed."""
        return await self.update(
            research_id,
            status="failed",
            final_answer=error,
            completed_at=datetime.utcnow(),
        )
    
    async def delete(self, research_id: int) -> bool:
        """Delete research run."""
        research = await self.get(research_id)
        if research:
            await self.session.delete(research)
            await self.session.flush()
            return True
        return False
