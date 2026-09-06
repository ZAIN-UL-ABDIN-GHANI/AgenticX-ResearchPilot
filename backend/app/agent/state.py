"""
LangGraph state schema for the ResearchPilot research agent.

This TypedDict is the single object threaded through every node of the
LangGraph StateGraph (see app/agent/graph.py). Only plain, JSON-serializable
data lives here -- database sessions, repositories, and tool singletons are
injected into the graph via closures (AgentContext), not through this state,
which keeps the graph itself pure and easy to test/replay.
"""

from typing import Any, Dict, List, Optional, TypedDict


class ResearchState(TypedDict, total=False):
    """State object threaded through the LangGraph research graph."""

    # Immutable inputs
    question: str
    research_run_id: int
    max_steps: int

    # Step bookkeeping (hard step-limit enforcement lives here)
    step_count: int

    # Search bookkeeping
    queries_tried: List[str]
    search_results: List[Dict[str, Any]]  # raw SearchResult dicts (source_id, url, title, snippet, domain)

    # Fetch bookkeeping: source_id -> FetchPageResponse dict
    fetched: Dict[str, Dict[str, Any]]

    # Summarize bookkeeping: source_ids that have already been summarized
    summarized: List[str]

    # Errors collected along the way (never fatal on their own)
    tool_errors: List[str]

    # Planner decision for the current iteration
    next_action: str  # "search" | "fetch" | "summarize" | "finish"

    # Terminal state
    final_answer: Optional[str]
    status: str  # "running" | "completed" | "failed" | "step_limit_reached"


def initial_state(question: str, research_run_id: int, max_steps: int) -> ResearchState:
    """Build the initial state for a new research run."""
    return ResearchState(
        question=question,
        research_run_id=research_run_id,
        max_steps=max_steps,
        step_count=0,
        queries_tried=[],
        search_results=[],
        fetched={},
        summarized=[],
        tool_errors=[],
        next_action="search",
        final_answer=None,
        status="running",
    )
