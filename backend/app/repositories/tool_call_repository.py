"""
Repository for tool_calls table operations.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ToolCall
from app.core.logging import get_logger

logger = get_logger(__name__)


class ToolCallRepository:
    """Repository for tool call data access."""
    
    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session
    
    async def create(
        self,
        research_run_id: int,
        tool_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        step_number: Optional[int] = None,
        status: str = "success",
    ) -> ToolCall:
        """Create a new tool call record."""
        tool_call = ToolCall(
            research_run_id=research_run_id,
            tool_name=tool_name,
            input_data=input_data,
            output_data=output_data,
            step_number=step_number,
            status=status,
        )
        self.session.add(tool_call)
        await self.session.flush()
        logger.info(
            f"Tool call recorded",
            extra={
                "tool": tool_name,
                "step": step_number,
                "status": status,
            },
        )
        return tool_call
    
    async def get(self, tool_call_id: int) -> Optional[ToolCall]:
        """Get tool call by ID."""
        result = await self.session.execute(
            select(ToolCall).where(ToolCall.id == tool_call_id)
        )
        return result.scalars().first()
    
    async def get_by_research(self, research_run_id: int) -> List[ToolCall]:
        """Get all tool calls for a research run."""
        result = await self.session.execute(
            select(ToolCall)
            .where(ToolCall.research_run_id == research_run_id)
            .order_by(ToolCall.step_number)
        )
        return result.scalars().all()
    
    async def get_by_tool(self, research_run_id: int, tool_name: str) -> List[ToolCall]:
        """Get tool calls by tool name."""
        result = await self.session.execute(
            select(ToolCall)
            .where(
                (ToolCall.research_run_id == research_run_id) &
                (ToolCall.tool_name == tool_name)
            )
            .order_by(ToolCall.step_number)
        )
        return result.scalars().all()
    
    async def get_step_count(self, research_run_id: int) -> int:
        """Get total tool call count for research."""
        result = await self.session.execute(
            select(ToolCall).where(ToolCall.research_run_id == research_run_id)
        )
        return len(result.scalars().all())
    
    async def update(self, tool_call_id: int, **kwargs) -> Optional[ToolCall]:
        """Update tool call."""
        from sqlalchemy import update
        await self.session.execute(
            update(ToolCall)
            .where(ToolCall.id == tool_call_id)
            .values(**kwargs)
        )
        await self.session.flush()
        return await self.get(tool_call_id)
    
    async def delete(self, tool_call_id: int) -> bool:
        """Delete tool call."""
        tool_call = await self.get(tool_call_id)
        if tool_call:
            await self.session.delete(tool_call)
            await self.session.flush()
            return True
        return False
