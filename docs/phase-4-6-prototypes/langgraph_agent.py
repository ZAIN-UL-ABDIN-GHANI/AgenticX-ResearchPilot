"""
LangGraph Research Agent - Main orchestration engine.

Implements:
- State machine with LangGraph
- Tool nodes (web search, fetch page, summarize)
- Planner node (decides which tool to call)
- Hard step limit enforcement
- Error recovery
- Final answer generation
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from agent_state import (
    AgentState,
    StateManager,
    ToolType,
    ExecutionStatus,
    SearchResult,
    FetchedPage,
    Summary,
)

logger = logging.getLogger(__name__)


class ResearchAgent:
    """Main research agent using LangGraph state machine."""

    def __init__(self, max_steps: int = 8):
        """Initialize research agent.

        Args:
            max_steps: Maximum steps allowed (hard limit)
        """
        self.max_steps = max_steps
        self.state: Optional[AgentState] = None
        logger.info(f"ResearchAgent initialized with max_steps={max_steps}")

    def initialize_research(
        self,
        question: str,
        research_id: Optional[str] = None,
        research_run_id: Optional[int] = None,
    ) -> AgentState:
        """Initialize new research.

        Args:
            question: Research question
            research_id: Research identifier
            research_run_id: Database run ID

        Returns:
            Initial agent state
        """
        self.state = StateManager.create_initial_state(
            question=question,
            max_steps=self.max_steps,
            research_id=research_id,
            research_run_id=research_run_id,
        )
        self.state.created_at = datetime.utcnow().isoformat()
        return self.state

    def plan_next_action(self, state: AgentState) -> Dict[str, Any]:
        """Plan next action based on current state (Planner Node).

        Args:
            state: Current agent state

        Returns:
            Decision dict with next action
        """
        state.increment_step()

        if state.steps_exceeded:
            logger.info("Step limit reached, forcing finish")
            return {"next_tool": ToolType.FINISH, "reasoning": "Step limit reached"}

        next_tool = StateManager.get_next_tool_decision(state)

        reasoning = self._generate_reasoning(state, next_tool)
        state.internal_reasoning = reasoning

        logger.debug(f"Plan: Next tool = {next_tool.value}, Reasoning: {reasoning}")

        return {"next_tool": next_tool, "reasoning": reasoning}

    def execute_web_search(
        self, state: AgentState, query: str
    ) -> Dict[str, Any]:
        """Execute web search tool.

        Args:
            state: Agent state
            query: Search query

        Returns:
            Tool result with search results
        """
        logger.info(f"Executing web_search: {query}")

        try:
            # This would call actual web search tool
            # For now, simulating results
            results = self._simulate_web_search(query)

            state.add_search_results(results)

            tool_call = state.add_tool_call(
                ToolType.WEB_SEARCH,
                {"query": query},
            )

            state.update_tool_result(
                {
                    "results_count": len(results),
                    "results": [
                        {
                            "source_id": r.source_id,
                            "title": r.title,
                            "url": r.url,
                            "snippet": r.snippet,
                        }
                        for r in results
                    ],
                }
            )

            return {
                "success": True,
                "tool_type": ToolType.WEB_SEARCH,
                "results": results,
                "result_count": len(results),
            }

        except Exception as e:
            error_msg = f"Web search failed: {str(e)}"
            state.add_error(error_msg)
            state.last_tool_error = error_msg

            state.add_tool_call(ToolType.WEB_SEARCH, {"query": query})
            state.update_tool_result({}, error=error_msg)

            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def execute_fetch_page(
        self, state: AgentState, url: str, source_id: str
    ) -> Dict[str, Any]:
        """Execute fetch page tool.

        Args:
            state: Agent state
            url: URL to fetch
            source_id: Source identifier

        Returns:
            Tool result with fetched content
        """
        logger.info(f"Executing fetch_page: {url}")

        try:
            # This would call actual fetch tool
            page = self._simulate_fetch_page(url, source_id)

            state.add_fetched_page(page)

            tool_call = state.add_tool_call(
                ToolType.FETCH_PAGE,
                {"url": url, "source_id": source_id},
            )

            state.update_tool_result(
                {
                    "source_id": page.source_id,
                    "url": page.url,
                    "title": page.title,
                    "word_count": page.word_count,
                    "fetch_status": page.fetch_status,
                }
            )

            return {
                "success": True,
                "tool_type": ToolType.FETCH_PAGE,
                "page": page,
            }

        except Exception as e:
            error_msg = f"Page fetch failed for {url}: {str(e)}"
            state.add_error(error_msg)
            state.last_tool_error = error_msg

            state.add_tool_call(
                ToolType.FETCH_PAGE,
                {"url": url, "source_id": source_id},
            )
            state.update_tool_result({}, error=error_msg)

            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def execute_summarize(
        self, state: AgentState, source_id: str, content: str
    ) -> Dict[str, Any]:
        """Execute summarize tool.

        Args:
            state: Agent state
            source_id: Source identifier
            content: Content to summarize

        Returns:
            Tool result with summary
        """
        logger.info(f"Executing summarize: {source_id}")

        try:
            # This would call actual summarize tool
            summary = self._simulate_summarize(source_id, content)

            state.add_summary(summary)

            tool_call = state.add_tool_call(
                ToolType.SUMMARIZE,
                {"source_id": source_id, "content_length": len(content)},
            )

            state.update_tool_result(
                {
                    "source_id": summary.source_id,
                    "summary": summary.summary[:200],
                    "claims_count": len(summary.key_claims),
                    "evidence_snippets": len(summary.evidence_snippets),
                }
            )

            return {
                "success": True,
                "tool_type": ToolType.SUMMARIZE,
                "summary": summary,
            }

        except Exception as e:
            error_msg = f"Summarization failed for {source_id}: {str(e)}"
            state.add_error(error_msg)
            state.last_tool_error = error_msg

            state.add_tool_call(
                ToolType.SUMMARIZE,
                {"source_id": source_id},
            )
            state.update_tool_result({}, error=error_msg)

            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def finalize_research(self, state: AgentState) -> Dict[str, Any]:
        """Finalize research and generate answer (Finish Node).

        Args:
            state: Final agent state

        Returns:
            Final answer with citations
        """
        logger.info("Finalizing research")

        state.research_complete = True
        state.status = ExecutionStatus.COMPLETED
        state.completed_at = datetime.utcnow().isoformat()

        # Generate final answer from summaries
        final_answer = self._generate_final_answer(state)
        state.final_answer = final_answer

        # Build citations
        citations = self._build_citations(state)
        state.citations = citations

        logger.info(f"Research completed: {len(state.summaries)} sources, {len(state.errors)} errors")

        return {
            "final_answer": final_answer,
            "citations": citations,
            "sources_used": len(state.summaries),
            "steps_used": state.step_count,
        }

    # ========================================================================
    # Simulation Methods (would be replaced with actual tool calls)
    # ========================================================================

    def _simulate_web_search(self, query: str) -> List[SearchResult]:
        """Simulate web search results.

        Args:
            query: Search query

        Returns:
            Mock search results
        """
        # In production, this would call actual search API
        results = [
            SearchResult(
                source_id=f"SRC-{i:03d}",
                title=f"Research Article {i+1}: {query}",
                url=f"https://example.com/article-{i+1}",
                snippet=f"This article discusses {query}. It contains relevant information...",
                rank=i + 1,
            )
            for i in range(3)
        ]
        return results

    def _simulate_fetch_page(self, url: str, source_id: str) -> FetchedPage:
        """Simulate page fetching.

        Args:
            url: URL to fetch
            source_id: Source identifier

        Returns:
            Mock fetched page
        """
        # In production, this would call actual fetch tool
        content = f"""
        Article from {url}

        This is research content on the topic. 
        Studies show important findings related to the research question.
        Evidence suggests that the conclusions are well-supported.
        """

        return FetchedPage(
            source_id=source_id,
            url=url,
            title=f"Title from {url}",
            domain=url.split("/")[2] if url else "example.com",
            content=content,
            word_count=len(content.split()),
            fetch_status="success",
        )

    def _simulate_summarize(self, source_id: str, content: str) -> Summary:
        """Simulate content summarization.

        Args:
            source_id: Source identifier
            content: Content to summarize

        Returns:
            Mock summary
        """
        # In production, this would call actual summarize tool via Gemini
        return Summary(
            source_id=source_id,
            summary=f"Summary of content from {source_id}: {content[:100]}...",
            key_claims=[
                "Finding 1 from research",
                "Finding 2 from research",
            ],
            evidence_snippets=[
                "Evidence snippet 1",
                "Evidence snippet 2",
            ],
            is_verified=True,
        )

    def _generate_reasoning(self, state: AgentState, next_tool: ToolType) -> str:
        """Generate reasoning for next action.

        Args:
            state: Current state
            next_tool: Next tool to execute

        Returns:
            Reasoning string
        """
        if next_tool == ToolType.WEB_SEARCH:
            return f"No search results yet for '{state.question}'. Starting web search."

        if next_tool == ToolType.FETCH_PAGE:
            unfetched = len(state.search_results) - len(state.fetched_pages)
            return f"Found {unfetched} sources to fetch. Fetching next page."

        if next_tool == ToolType.SUMMARIZE:
            unsummarized = len(state.fetched_pages) - len(state.summaries)
            return f"Have {unsummarized} pages to summarize. Extracting evidence."

        if next_tool == ToolType.FINISH:
            if state.steps_exceeded:
                return f"Step limit reached ({state.step_count}/{state.max_steps}). Generating final answer."
            return f"Collected sufficient evidence. Generating final answer."

        return f"Next action: {next_tool.value}"

    def _generate_final_answer(self, state: AgentState) -> str:
        """Generate final answer from collected evidence.

        Args:
            state: Final state

        Returns:
            Final answer
        """
        if not state.summaries:
            return "Unable to generate answer: no sources were successfully processed."

        answer_parts = [f"Based on research into: {state.question}\n"]

        answer_parts.append("Key findings:\n")
        for i, summary in enumerate(state.summaries, 1):
            answer_parts.append(f"{i}. {summary.summary[:150]}...\n")

        answer_parts.append(f"\nResearch completed using {len(state.summaries)} sources in {state.step_count} steps.")

        return "".join(answer_parts)

    def _build_citations(self, state: AgentState) -> Dict[str, Any]:
        """Build citations from processed sources.

        Args:
            state: Final state

        Returns:
            Citations dictionary
        """
        citations = {}

        for i, summary in enumerate(state.summaries, 1):
            fetched_page = next(
                (fp for fp in state.fetched_pages if fp.source_id == summary.source_id),
                None,
            )

            if fetched_page:
                citations[f"[{i}]"] = {
                    "source_id": summary.source_id,
                    "title": fetched_page.title,
                    "url": fetched_page.url,
                    "domain": fetched_page.domain,
                }

        return citations

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary.

        Returns:
            State summary
        """
        if not self.state:
            return {"error": "No active research"}

        return self.state.get_summary()

    def export_state(self) -> Dict[str, Any]:
        """Export complete state for persistence.

        Returns:
            Complete state dictionary
        """
        if not self.state:
            return {}

        return self.state.to_dict()


# ============================================================================
# Agent Graph Builder
# ============================================================================


class AgentGraphBuilder:
    """Builds LangGraph state machine for research agent."""

    @staticmethod
    def build_research_graph() -> Dict[str, Any]:
        """Build the research agent graph.

        Returns:
            Graph definition (nodes and edges)
        """
        graph_definition = {
            "nodes": {
                "planner": {
                    "type": "decision",
                    "description": "Decide which tool to call next",
                },
                "web_search": {
                    "type": "tool",
                    "description": "Search for sources",
                },
                "fetch_page": {
                    "type": "tool",
                    "description": "Fetch page content",
                },
                "summarize": {
                    "type": "tool",
                    "description": "Summarize content",
                },
                "finalize": {
                    "type": "finish",
                    "description": "Generate final answer",
                },
            },
            "edges": {
                "START": "planner",
                "planner": [
                    ("web_search", "next_tool == WEB_SEARCH"),
                    ("fetch_page", "next_tool == FETCH_PAGE"),
                    ("summarize", "next_tool == SUMMARIZE"),
                    ("finalize", "next_tool == FINISH"),
                ],
                "web_search": "planner",
                "fetch_page": "planner",
                "summarize": "planner",
                "finalize": "END",
            },
        }

        return graph_definition
