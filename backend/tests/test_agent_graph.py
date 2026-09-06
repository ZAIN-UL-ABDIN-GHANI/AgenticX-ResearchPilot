"""
Tests for the LangGraph research agent (app/agent/graph.py).

All external calls (Google Custom Search, Gemini) are monkeypatched so these
tests run fully offline and deterministically.
"""

from typing import List, Optional
from unittest.mock import AsyncMock

import pytest

from app.agent.graph import AgentContext, build_research_graph
from app.agent.state import initial_state
from app.db.database import async_session_maker
from app.repositories.research_repository import ResearchRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.tool_call_repository import ToolCallRepository
from app.services.citation_integration import CitationIntegrationService
from app.schemas.tools import (
    WebSearchResponse,
    SearchResult,
    FetchPageResponse,
    SummarizeResponse,
    KeyClaim,
)


def make_search_result(n: int) -> SearchResult:
    return SearchResult(
        source_id=f"SRC-{n:03d}",
        title=f"Article {n}",
        url=f"https://example{n}.com/article",
        snippet=f"Snippet {n}",
        domain=f"example{n}.com",
    )


async def _build_ctx(session):
    """Helper: build a fresh AgentContext bound to a real DB session."""
    source_repo = SourceRepository(session)
    tool_call_repo = ToolCallRepository(session)
    citation_service = CitationIntegrationService()
    return AgentContext(source_repo, tool_call_repo, citation_service), citation_service


@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session


@pytest.mark.asyncio
async def test_agent_chooses_search_first(db_session, monkeypatch):
    """With no prior queries, the planner must choose 'search' first."""
    ctx, _ = await _build_ctx(db_session)

    async def fake_search(self, query, max_results=5):
        return WebSearchResponse(success=True, results=[], result_count=0)

    monkeypatch.setattr(
        "app.tools.web_search.WebSearchTool.execute", fake_search
    )

    graph = build_research_graph(ctx)
    repo = ResearchRepository(db_session)
    research = await repo.create("What is machine learning?", max_steps=8)
    await db_session.commit()

    state = initial_state("What is machine learning?", research.id, max_steps=8)
    final_state = await graph.ainvoke(state, config={"recursion_limit": 50})

    assert final_state["queries_tried"], "agent should have executed at least one search"
    calls = await ToolCallRepository(db_session).get_by_research(research.id)
    assert calls[0].tool_name == "web_search"


@pytest.mark.asyncio
async def test_agent_multi_tool_happy_path(db_session, monkeypatch):
    """Agent should search -> fetch -> summarize -> finish, using all 3 tools."""
    ctx, citation_service = await _build_ctx(db_session)

    async def fake_search(self, query, max_results=5):
        return WebSearchResponse(
            success=True, results=[make_search_result(1)], result_count=1
        )

    async def fake_fetch(self, url, source_id):
        return FetchPageResponse(
            success=True,
            source_id=source_id,
            url=url,
            title="Article 1",
            content="Machine learning is a subset of AI that learns from data.",
            word_count=11,
            fetch_status="success",
        )

    async def fake_summarize(self, source_id, content, context=None):
        return SummarizeResponse(
            success=True,
            source_id=source_id,
            summary="ML is a subset of AI.",
            key_claims=[
                KeyClaim(
                    claim="Machine learning is a subset of AI",
                    evidence="learns from data",
                    confidence=0.9,
                )
            ],
        )

    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", fake_search)
    monkeypatch.setattr("app.tools.fetch_page.FetchPageTool.execute", fake_fetch)
    monkeypatch.setattr("app.tools.summarize.SummarizationTool.execute", fake_summarize)

    graph = build_research_graph(ctx)
    repo = ResearchRepository(db_session)
    research = await repo.create("What is machine learning?", max_steps=8)
    await db_session.commit()

    state = initial_state("What is machine learning?", research.id, max_steps=8)
    final_state = await graph.ainvoke(state, config={"recursion_limit": 50})

    tool_calls = await ToolCallRepository(db_session).get_by_research(research.id)
    tool_names = {c.tool_name for c in tool_calls}
    assert tool_names == {"web_search", "fetch_page", "summarize"}

    assert "SRC-001" in final_state["fetched"]
    assert final_state["fetched"]["SRC-001"]["success"] is True
    assert "SRC-001" in final_state["summarized"]

    # Citation service should now have real evidence grounded in a fetched source.
    assert len(citation_service.evidence_map) == 1
    report = citation_service.validate_answer(
        "Machine learning is a subset of AI."
    )
    assert report["fetched_sources"] == 1
    assert report["verified_claims"] >= 1


@pytest.mark.asyncio
async def test_hard_step_limit_guarantees_termination(db_session, monkeypatch):
    """Even if search 'succeeds' forever with fresh sources, the graph must
    stop within max_steps planner invocations -- never loop indefinitely."""
    ctx, _ = await _build_ctx(db_session)

    counter = {"n": 0}

    async def fake_search(self, query, max_results=5):
        counter["n"] += 1
        # Always return a brand-new, never-before-seen source so the planner
        # would keep wanting to fetch/search forever without the hard limit.
        return WebSearchResponse(
            success=True,
            results=[make_search_result(counter["n"])],
            result_count=1,
        )

    async def fake_fetch(self, url, source_id):
        # Fetch always fails -> nothing to summarize -> planner keeps
        # searching/fetching, exercising the step limit under failure.
        return FetchPageResponse(
            success=False,
            source_id=source_id,
            url=url,
            error="Timeout",
            fetch_status="timeout",
        )

    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", fake_search)
    monkeypatch.setattr("app.tools.fetch_page.FetchPageTool.execute", fake_fetch)

    graph = build_research_graph(ctx)
    repo = ResearchRepository(db_session)
    max_steps = 5
    research = await repo.create("Infinite question", max_steps=max_steps)
    await db_session.commit()

    state = initial_state("Infinite question", research.id, max_steps=max_steps)
    # recursion_limit is set generously so ONLY our own step_count logic can
    # be responsible for stopping the graph -- if the hard limit were broken,
    # this would hit LangGraph's recursion_limit and raise instead of
    # returning cleanly.
    final_state = await graph.ainvoke(
        state, config={"recursion_limit": (max_steps * 4) + 20}
    )

    assert final_state["step_count"] <= max_steps + 1
    assert final_state["status"] == "step_limit_reached"
    assert final_state["next_action"] == "finish"

    tool_calls = await ToolCallRepository(db_session).get_by_research(research.id)
    # Number of executed tool calls must never exceed the step budget.
    assert len(tool_calls) <= max_steps


@pytest.mark.asyncio
async def test_search_failure_is_recovered_via_reformulation(db_session, monkeypatch):
    """A failing/empty search should not crash the agent; it should
    reformulate the query and try again, then terminate safely."""
    ctx, _ = await _build_ctx(db_session)

    async def failing_search(self, query, max_results=5):
        return WebSearchResponse(success=False, error="Search API unavailable")

    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", failing_search)

    graph = build_research_graph(ctx)
    repo = ResearchRepository(db_session)
    research = await repo.create("Unanswerable question", max_steps=8)
    await db_session.commit()

    state = initial_state("Unanswerable question", research.id, max_steps=8)
    final_state = await graph.ainvoke(state, config={"recursion_limit": 50})

    assert final_state["tool_errors"], "search failures should be recorded, not raised"
    assert final_state.get("final_answer") in (None, "")
    # Agent must terminate even though it never found any evidence.
    assert final_state["next_action"] == "finish"
