"""
LangGraph research agent.

This module builds the actual `langgraph.graph.StateGraph` that orchestrates
the three research tools (web_search, fetch_page, summarize). It is the
central agentic component required by the project spec:

    START -> planner -> {search | fetch | summarize} -> planner -> ... -> finish -> END

Design notes
------------
* The graph state (``ResearchState``) is a plain TypedDict so it stays
  serializable and easy to unit test / replay.
* Database sessions, repositories and the citation service are NOT part of
  the graph state (they are not JSON-serializable and shouldn't be). Instead
  they are injected once via ``AgentContext`` and closed over by the node
  functions built in ``build_research_graph``.
* The hard step limit is enforced programmatically in ``planner_node``: once
  ``step_count`` exceeds ``max_steps`` the planner *always* routes to
  ``finish`` regardless of what the graph "wants" to do next. This guarantees
  termination even under tool failures or repeated empty search results.
"""

from typing import Any, Dict, List
from urllib.parse import urlparse

from langgraph.graph import StateGraph, END

from app.agent.state import ResearchState
from app.core.logging import get_logger
from app.repositories.source_repository import SourceRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.services.citation_integration import CitationIntegrationService
from app.tools.web_search import get_web_search_tool
from app.tools.fetch_page import get_fetch_page_tool
from app.tools.summarize import get_summarization_tool

logger = get_logger(__name__)

# How many top search results we bother fetching per query before
# reformulating / moving on. Keeps a single search from exhausting the
# entire step budget on one query.
MAX_FETCH_PER_QUERY = 3
MAX_QUERY_REFORMULATIONS = 2


class AgentContext:
    """Dependencies injected into the graph's node closures.

    Keeping these off the LangGraph state on purpose -- see module docstring.
    """

    def __init__(
        self,
        source_repo: SourceRepository,
        tool_call_repo: ToolCallRepository,
        citation_service: CitationIntegrationService,
    ) -> None:
        self.source_repo = source_repo
        self.tool_call_repo = tool_call_repo
        self.citation_service = citation_service
        # Maps our human-readable source_id (e.g. "SRC-001") to the
        # database primary key of the `sources` row, so tool results can be
        # persisted without re-querying.
        self.source_pk: Dict[str, int] = {}


def _reformulate_query(question: str, tried: List[str]) -> str:
    """Produce a different search query after a previous one under-delivered."""
    if len(tried) == 0:
        return question
    if len(tried) == 1:
        return f"{question} explained"
    return f"{question} recent research overview"


def build_research_graph(ctx: AgentContext):
    """Build and compile the LangGraph StateGraph for the research agent.

    Returns a compiled graph exposing ``.ainvoke(state, config=...)``.
    """

    async def planner_node(state: ResearchState) -> ResearchState:
        """Decide the next tool to call, or whether to finish.

        This is the ONLY place step_count is incremented, and the ONLY place
        that is allowed to route to "finish" because of the step budget.
        The limit is enforced with a plain integer comparison -- never left
        to an LLM's discretion -- so termination is guaranteed.
        """
        step_count = state.get("step_count", 0) + 1
        state["step_count"] = step_count

        if step_count > state["max_steps"]:
            logger.info(
                "Hard step limit reached (%s/%s) - forcing finish",
                step_count,
                state["max_steps"],
            )
            state["next_action"] = "finish"
            state["status"] = "step_limit_reached"
            return state

        search_results = state.get("search_results", [])
        fetched = state.get("fetched", {})
        summarized = state.get("summarized", [])
        queries_tried = state.get("queries_tried", [])

        unfetched = [r for r in search_results if r["source_id"] not in fetched]
        successfully_fetched = [
            sid for sid, data in fetched.items() if data.get("success")
        ]
        unsummarized = [sid for sid in successfully_fetched if sid not in summarized]

        if not queries_tried:
            next_action = "search"
        elif unfetched:
            next_action = "fetch"
        elif unsummarized:
            next_action = "summarize"
        elif not successfully_fetched and len(queries_tried) <= MAX_QUERY_REFORMULATIONS:
            # Search came back empty/unusable so far -> reformulate and retry.
            next_action = "search"
        else:
            next_action = "finish"

        state["next_action"] = next_action
        logger.debug("Planner step %s -> %s", step_count, next_action)
        return state

    async def search_node(state: ResearchState) -> ResearchState:
        """Tool node: web search. Persists sources and tracks them for citation."""
        tool = get_web_search_tool()
        query = _reformulate_query(state["question"], state.get("queries_tried", []))

        result = await tool.execute(query=query, max_results=5)
        state.setdefault("queries_tried", []).append(query)

        await ctx.tool_call_repo.create(
            research_run_id=state["research_run_id"],
            tool_name="web_search",
            input_data={"query": query, "max_results": 5},
            output_data=result.model_dump(),
            step_number=state["step_count"],
            status="success" if result.success else "error",
        )

        if not result.success:
            state.setdefault("tool_errors", []).append(f"search: {result.error}")
            return state

        await ctx.citation_service.add_search_source(result)

        existing_ids = {r["source_id"] for r in state.get("search_results", [])}
        for r in result.results[:MAX_FETCH_PER_QUERY]:
            if r.source_id in existing_ids:
                continue
            state.setdefault("search_results", []).append(r.model_dump())
            db_source = await ctx.source_repo.create(
                research_run_id=state["research_run_id"],
                source_id=r.source_id,
                url=r.url,
                title=r.title,
                domain=r.domain or urlparse(r.url).netloc,
            )
            ctx.source_pk[r.source_id] = db_source.id

        return state

    async def fetch_node(state: ResearchState) -> ResearchState:
        """Tool node: fetch page. Never treats an unfetched source as evidence."""
        tool = get_fetch_page_tool()
        search_results = state.get("search_results", [])
        fetched = state.get("fetched", {})
        unfetched = [r for r in search_results if r["source_id"] not in fetched]

        if not unfetched:
            return state

        target = unfetched[0]
        result = await tool.execute(url=target["url"], source_id=target["source_id"])

        await ctx.tool_call_repo.create(
            research_run_id=state["research_run_id"],
            tool_name="fetch_page",
            input_data={"url": target["url"], "source_id": target["source_id"]},
            output_data=result.model_dump(),
            step_number=state["step_count"],
            status="success" if result.success else "error",
        )

        state.setdefault("fetched", {})[target["source_id"]] = result.model_dump()
        await ctx.citation_service.add_fetched_source(result)

        db_id = ctx.source_pk.get(target["source_id"])
        if db_id is not None:
            if result.success:
                await ctx.source_repo.mark_fetched(
                    db_id, result.content or "", result.word_count or 0
                )
            else:
                await ctx.source_repo.mark_fetch_error(db_id, result.error or "unknown error")

        if not result.success:
            state.setdefault("tool_errors", []).append(
                f"fetch:{target['source_id']}: {result.error}"
            )

        return state

    async def summarize_node(state: ResearchState) -> ResearchState:
        """Tool node: summarize/evidence extraction. Retries once on failure."""
        tool = get_summarization_tool()
        fetched = state.get("fetched", {})
        summarized = state.get("summarized", [])

        candidates = [
            sid
            for sid, data in fetched.items()
            if data.get("success") and sid not in summarized
        ]
        if not candidates:
            return state

        source_id = candidates[0]
        content = fetched[source_id].get("content") or ""

        result = await tool.execute(
            source_id=source_id, content=content, context=state["question"]
        )

        # Retry once on failure per the spec's failure-handling policy.
        if not result.success:
            logger.warning("Summarize failed for %s, retrying once", source_id)
            result = await tool.execute(
                source_id=source_id, content=content, context=state["question"]
            )

        await ctx.tool_call_repo.create(
            research_run_id=state["research_run_id"],
            tool_name="summarize",
            input_data={"source_id": source_id},
            output_data=result.model_dump(),
            step_number=state["step_count"],
            status="success" if result.success else "error",
        )

        state.setdefault("summarized", []).append(source_id)

        if result.success:
            await ctx.citation_service.add_evidence_from_summary(source_id, result)
        else:
            state.setdefault("tool_errors", []).append(
                f"summarize:{source_id}: {result.error}"
            )

        return state

    def route_from_planner(state: ResearchState) -> str:
        return state.get("next_action", "finish")

    graph = StateGraph(ResearchState)
    graph.add_node("planner", planner_node)
    graph.add_node("search", search_node)
    graph.add_node("fetch", fetch_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "search": "search",
            "fetch": "fetch",
            "summarize": "summarize",
            "finish": END,
        },
    )
    graph.add_edge("search", "planner")
    graph.add_edge("fetch", "planner")
    graph.add_edge("summarize", "planner")

    return graph.compile()
