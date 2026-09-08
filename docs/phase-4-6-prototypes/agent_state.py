"""
LangGraph Agent State - Complete state management for research agent.

Tracks:
- Research question and metadata
- Tool decisions and results
- Evidence and claims
- Step budget and limits
- Agent execution flow
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ToolType(str, Enum):
    """Tool types available to agent."""
    
    WEB_SEARCH = "web_search"
    FETCH_PAGE = "fetch_page"
    SUMMARIZE = "summarize"
    THINK = "think"
    FINISH = "finish"


class ExecutionStatus(str, Enum):
    """Agent execution statuses."""
    
    INITIALIZED = "initialized"
    RESEARCHING = "researching"
    PROCESSING = "processing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    STEP_LIMIT_REACHED = "step_limit_reached"


@dataclass
class ToolCall:
    """Record of a tool call."""
    
    step_number: int
    tool_type: ToolType
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    success: bool = False
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step_number": self.step_number,
            "tool_type": self.tool_type.value,
            "input": self.input_data,
            "output": self.output_data,
            "error": self.error,
            "success": self.success,
            "timestamp": self.timestamp,
        }


@dataclass
class SearchResult:
    """Search result from web search tool."""
    
    source_id: str
    title: str
    url: str
    snippet: str
    rank: int


@dataclass
class FetchedPage:
    """Fetched page from fetch tool."""
    
    source_id: str
    url: str
    title: Optional[str]
    domain: Optional[str]
    content: str
    word_count: int
    fetch_status: str  # success, timeout, error, forbidden


@dataclass
class Summary:
    """Summary from summarize tool."""
    
    source_id: str
    summary: str
    key_claims: List[str]
    evidence_snippets: List[str]
    is_verified: bool


@dataclass
class AgentState:
    """Complete state for research agent.
    
    This is the central state object passed through the LangGraph execution.
    """
    
    # Research context
    research_id: Optional[str] = None
    question: str = ""
    research_run_id: Optional[int] = None
    
    # Step tracking (CRITICAL FOR STEP LIMIT)
    step_count: int = 0
    max_steps: int = 8
    steps_exceeded: bool = False
    
    # Execution status
    status: ExecutionStatus = ExecutionStatus.INITIALIZED
    
    # Messages/conversation
    messages: List[Dict[str, str]] = field(default_factory=list)
    internal_reasoning: str = ""
    
    # Tool execution history
    tool_calls: List[ToolCall] = field(default_factory=list)
    last_tool_type: Optional[ToolType] = None
    last_tool_error: Optional[str] = None
    
    # Search results
    search_results: List[SearchResult] = field(default_factory=list)
    sources_found: int = 0
    
    # Fetched sources
    fetched_pages: List[FetchedPage] = field(default_factory=list)
    sources_fetched: int = 0
    
    # Summaries and evidence
    summaries: List[Summary] = field(default_factory=list)
    extracted_claims: List[str] = field(default_factory=list)
    evidence_links: Dict[str, List[str]] = field(default_factory=dict)
    
    # RAG pipeline state
    rag_processed_sources: Dict[str, Any] = field(default_factory=dict)
    
    # Final output
    final_answer: Optional[str] = None
    citations: Dict[str, Any] = field(default_factory=dict)
    
    # Research decision state
    needs_more_research: bool = True
    research_complete: bool = False
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    
    # Research metadata
    created_at: Optional[str] = None
    completed_at: Optional[str] = None

    def increment_step(self) -> None:
        """Increment step counter and check limit."""
        self.step_count += 1
        logger.debug(f"Step {self.step_count}/{self.max_steps}")
        
        if self.step_count >= self.max_steps:
            self.steps_exceeded = True
            self.status = ExecutionStatus.STEP_LIMIT_REACHED
            logger.warning(f"Step limit reached: {self.step_count}/{self.max_steps}")

    def can_continue(self) -> bool:
        """Check if agent can continue executing.
        
        Returns:
            False if step limit reached or status is terminal
        """
        if self.steps_exceeded:
            return False
        
        if self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
            return False
        
        return self.step_count < self.max_steps

    def add_tool_call(
        self,
        tool_type: ToolType,
        input_data: Dict[str, Any],
    ) -> ToolCall:
        """Add tool call to history.
        
        Args:
            tool_type: Type of tool being called
            input_data: Input to the tool
            
        Returns:
            ToolCall object
        """
        tool_call = ToolCall(
            step_number=self.step_count,
            tool_type=tool_type,
            input_data=input_data,
        )
        self.tool_calls.append(tool_call)
        self.last_tool_type = tool_type
        return tool_call

    def update_tool_result(
        self,
        output_data: Dict[str, Any],
        error: Optional[str] = None,
    ) -> None:
        """Update last tool call with result.
        
        Args:
            output_data: Output from the tool
            error: Error message if tool failed
        """
        if not self.tool_calls:
            return
        
        last_call = self.tool_calls[-1]
        last_call.output_data = output_data
        last_call.success = error is None
        last_call.error = error
        
        if error:
            self.last_tool_error = error
            self.errors.append(error)

    def add_search_results(self, results: List[SearchResult]) -> None:
        """Add search results to state.
        
        Args:
            results: List of search results
        """
        self.search_results.extend(results)
        self.sources_found = len(self.search_results)
        logger.info(f"Search results: {len(results)} sources found")

    def add_fetched_page(self, page: FetchedPage) -> None:
        """Add fetched page to state.
        
        Args:
            page: Fetched page
        """
        self.fetched_pages.append(page)
        self.sources_fetched = len(self.fetched_pages)
        logger.info(f"Page fetched: {page.source_id} ({page.word_count} words)")

    def add_summary(self, summary: Summary) -> None:
        """Add summary to state.
        
        Args:
            summary: Summary object
        """
        self.summaries.append(summary)
        logger.info(f"Summary added: {summary.source_id}")

    def add_error(self, error: str) -> None:
        """Add error to state.
        
        Args:
            error: Error message
        """
        self.errors.append(error)
        logger.warning(f"Error: {error}")

    def get_summary(self) -> Dict[str, Any]:
        """Get state summary for logging/debugging.
        
        Returns:
            Summary dictionary
        """
        return {
            "research_id": self.research_id,
            "question": self.question[:100],
            "status": self.status.value,
            "step_count": f"{self.step_count}/{self.max_steps}",
            "steps_exceeded": self.steps_exceeded,
            "sources_found": self.sources_found,
            "sources_fetched": self.sources_fetched,
            "summaries": len(self.summaries),
            "tool_calls": len(self.tool_calls),
            "errors": len(self.errors),
            "research_complete": self.research_complete,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert complete state to dictionary.
        
        Returns:
            Dictionary representation of state
        """
        return {
            "research_id": self.research_id,
            "question": self.question,
            "step_count": self.step_count,
            "max_steps": self.max_steps,
            "status": self.status.value,
            "sources_found": self.sources_found,
            "sources_fetched": self.sources_fetched,
            "summaries_count": len(self.summaries),
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "errors": self.errors,
            "final_answer": self.final_answer,
            "research_complete": self.research_complete,
        }


class StateManager:
    """Manager for agent state operations."""

    @staticmethod
    def create_initial_state(
        question: str,
        max_steps: int = 8,
        research_id: Optional[str] = None,
        research_run_id: Optional[int] = None,
    ) -> AgentState:
        """Create initial agent state for research.
        
        Args:
            question: Research question
            max_steps: Maximum steps allowed
            research_id: Research ID
            research_run_id: Database research run ID
            
        Returns:
            Initial AgentState
        """
        state = AgentState(
            research_id=research_id,
            question=question,
            research_run_id=research_run_id,
            max_steps=max_steps,
            status=ExecutionStatus.INITIALIZED,
        )
        
        logger.info(
            f"Created initial state: question='{question[:50]}...', "
            f"max_steps={max_steps}"
        )
        
        return state

    @staticmethod
    def should_continue_research(state: AgentState) -> bool:
        """Determine if research should continue.
        
        Args:
            state: Current agent state
            
        Returns:
            True if research should continue
        """
        if not state.can_continue():
            return False
        
        if state.research_complete:
            return False
        
        # Continue if we have search results but haven't fetched them all
        if state.search_results and len(state.search_results) > len(state.fetched_pages):
            return True
        
        # Continue if we haven't done any research yet
        if len(state.tool_calls) == 0:
            return True
        
        # Continue if last action was a fetch and we haven't summarized
        if state.last_tool_type == ToolType.FETCH_PAGE and len(state.summaries) < len(state.fetched_pages):
            return True
        
        return False

    @staticmethod
    def get_next_tool_decision(state: AgentState) -> ToolType:
        """Decide which tool to call next based on state.
        
        Args:
            state: Current agent state
            
        Returns:
            Next tool to call
        """
        # If we've reached step limit, finish
        if state.steps_exceeded:
            return ToolType.FINISH
        
        # If no search results yet, search
        if not state.search_results:
            return ToolType.WEB_SEARCH
        
        # If we have search results but haven't fetched them, fetch
        unfetched = [
            sr for sr in state.search_results
            if sr.source_id not in [fp.source_id for fp in state.fetched_pages]
        ]
        
        if unfetched:
            return ToolType.FETCH_PAGE
        
        # If we have fetched pages but haven't summarized, summarize
        unsummarized = [
            fp for fp in state.fetched_pages
            if fp.source_id not in [s.source_id for s in state.summaries]
        ]
        
        if unsummarized:
            return ToolType.SUMMARIZE
        
        # We have enough evidence, finish
        if len(state.summaries) >= 2:
            return ToolType.FINISH
        
        # Default to finish if no clear path forward
        return ToolType.FINISH
