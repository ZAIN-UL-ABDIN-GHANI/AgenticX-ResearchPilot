"""
API integration tests for the /api/v1/research endpoints.

Uses httpx's ASGI transport to call the FastAPI app in-process (no real
network/server needed). The three tools are monkeypatched so the full
research workflow -- including the background LangGraph agent run -- proceeds
deterministically and offline.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.tools import (
    WebSearchResponse,
    SearchResult,
    FetchPageResponse,
    SummarizeResponse,
    KeyClaim,
)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_research_rejects_empty_question(client):
    response = await client.post("/api/v1/research", json={"question": "   "})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_research_rejects_too_long_question(client):
    response = await client.post(
        "/api/v1/research", json={"question": "x" * 501}
    )
    assert response.status_code == 422  # Pydantic max_length validation


@pytest.mark.asyncio
async def test_get_nonexistent_research_returns_404(client):
    response = await client.get("/api/v1/research/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_full_research_workflow_via_api(client, monkeypatch):
    """End-to-end: create research -> agent runs in background -> poll ->
    verify sources, tool calls, and claims are all reachable via the API and
    every claim is backed by a fetched source (NO SOURCE = NO CLAIM)."""

    async def fake_search(self, query, max_results=5):
        return WebSearchResponse(
            success=True,
            results=[
                SearchResult(
                    source_id="SRC-101",
                    title="RAG Explained",
                    url="https://example.com/rag",
                    snippet="RAG combines retrieval with generation",
                    domain="example.com",
                )
            ],
            result_count=1,
        )

    async def fake_fetch(self, url, source_id):
        return FetchPageResponse(
            success=True,
            source_id=source_id,
            url=url,
            title="RAG Explained",
            content=(
                "Retrieval-Augmented Generation (RAG) grounds language model "
                "answers in retrieved documents instead of relying purely on "
                "parametric memory."
            ),
            word_count=20,
            fetch_status="success",
        )

    async def fake_summarize(self, source_id, content, context=None):
        return SummarizeResponse(
            success=True,
            source_id=source_id,
            summary="RAG grounds answers in retrieved documents.",
            key_claims=[
                KeyClaim(
                    claim="RAG grounds answers in retrieved documents",
                    evidence=content[:80],
                    confidence=0.9,
                )
            ],
        )

    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", fake_search)
    monkeypatch.setattr("app.tools.fetch_page.FetchPageTool.execute", fake_fetch)
    monkeypatch.setattr(
        "app.tools.summarize.SummarizationTool.execute", fake_summarize
    )

    # Also stub the final-answer synthesis call so the test doesn't need a
    # live Gemini API key/network access.
    async def fake_generate_answer(self, question, citation_service):
        return "RAG grounds answers in retrieved documents."

    monkeypatch.setattr(
        "app.services.research_service.ResearchService._generate_answer",
        fake_generate_answer,
    )

    create_resp = await client.post(
        "/api/v1/research",
        json={"question": "What is RAG and why is it useful?", "max_steps": 8},
    )
    assert create_resp.status_code == 201
    research_id = create_resp.json()["research_id"]

    status_resp = await client.get(f"/api/v1/research/{research_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == "completed"
    assert body["final_answer"]
    assert "RAG" in body["final_answer"]

    sources_resp = await client.get(f"/api/v1/research/{research_id}/sources")
    assert sources_resp.status_code == 200
    sources = sources_resp.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["fetch_status"] == "success"

    tools_resp = await client.get(f"/api/v1/research/{research_id}/tools")
    assert tools_resp.status_code == 200
    tool_names = {t["tool_name"] for t in tools_resp.json()["tool_calls"]}
    assert tool_names == {"web_search", "fetch_page", "summarize"}

    claims_resp = await client.get(f"/api/v1/research/{research_id}/claims")
    assert claims_resp.status_code == 200
    claims = claims_resp.json()["claims"]
    assert len(claims) >= 1
    for claim in claims:
        # NO SOURCE = NO CLAIM: every persisted claim must cite >=1 source.
        assert len(claim["citations"]) >= 1
        for citation in claim["citations"]:
            assert citation["source_id"] == "SRC-101"
            assert citation["url"] == "https://example.com/rag"


@pytest.mark.asyncio
async def test_citations_isolated_across_research_runs(client, monkeypatch):
    """Regression test: two different research runs whose sources reuse the
    same human-readable source_id (e.g. both start at "SRC-001") must never
    have their claims/citations cross-contaminated. This guards against a
    real bug where SourceRepository.get_by_source_id() looked up a source by
    source_id alone (unique only *within* a run, not globally), which could
    attach a claim in one run to a completely different run's fetched
    source."""

    def make_fakes(url: str, title: str, content: str):
        async def fake_search(self, query, max_results=5):
            return WebSearchResponse(
                success=True,
                results=[
                    SearchResult(
                        source_id="SRC-001", title=title, url=url,
                        snippet=title, domain="example.com",
                    )
                ],
                result_count=1,
            )

        async def fake_fetch(self, url, source_id):
            return FetchPageResponse(
                success=True, source_id=source_id, url=url, title=title,
                content=content, word_count=len(content.split()),
                fetch_status="success",
            )

        async def fake_summarize(self, source_id, content, context=None):
            return SummarizeResponse(
                success=True, source_id=source_id, summary=title,
                key_claims=[KeyClaim(claim=title, evidence=content[:60], confidence=0.9)],
            )

        return fake_search, fake_fetch, fake_summarize

    async def fake_generate_answer_a(self, question, citation_service):
        return "Topic A Source."

    async def fake_generate_answer_b(self, question, citation_service):
        return "Topic B Source."

    # --- Run A ---
    search_a, fetch_a, summarize_a = make_fakes(
        "https://a.example.com", "Topic A Source", "Evidence supporting topic A."
    )
    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", search_a)
    monkeypatch.setattr("app.tools.fetch_page.FetchPageTool.execute", fetch_a)
    monkeypatch.setattr("app.tools.summarize.SummarizationTool.execute", summarize_a)
    monkeypatch.setattr(
        "app.services.research_service.ResearchService._generate_answer",
        fake_generate_answer_a,
    )
    resp_a = await client.post("/api/v1/research", json={"question": "Topic A?", "max_steps": 8})
    run_a_id = resp_a.json()["research_id"]

    # --- Run B (reuses the same source_id "SRC-001", different URL/content) ---
    search_b, fetch_b, summarize_b = make_fakes(
        "https://b.example.com", "Topic B Source", "Evidence supporting topic B."
    )
    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", search_b)
    monkeypatch.setattr("app.tools.fetch_page.FetchPageTool.execute", fetch_b)
    monkeypatch.setattr("app.tools.summarize.SummarizationTool.execute", summarize_b)
    monkeypatch.setattr(
        "app.services.research_service.ResearchService._generate_answer",
        fake_generate_answer_b,
    )
    resp_b = await client.post("/api/v1/research", json={"question": "Topic B?", "max_steps": 8})
    run_b_id = resp_b.json()["research_id"]

    claims_a = (await client.get(f"/api/v1/research/{run_a_id}/claims")).json()["claims"]
    claims_b = (await client.get(f"/api/v1/research/{run_b_id}/claims")).json()["claims"]

    assert claims_a[0]["citations"][0]["url"] == "https://a.example.com"
    assert claims_b[0]["citations"][0]["url"] == "https://b.example.com"


@pytest.mark.asyncio
async def test_research_with_failing_search_reports_failure(client, monkeypatch):
    """If the search tool can never find anything, the run should complete
    as 'failed' with an honest message rather than fabricating an answer."""

    async def always_fails(self, query, max_results=5):
        return WebSearchResponse(success=False, error="Search API unavailable")

    monkeypatch.setattr("app.tools.web_search.WebSearchTool.execute", always_fails)

    create_resp = await client.post(
        "/api/v1/research", json={"question": "Unanswerable question", "max_steps": 4}
    )
    research_id = create_resp.json()["research_id"]

    status_resp = await client.get(f"/api/v1/research/{research_id}")
    body = status_resp.json()
    assert body["status"] == "failed"
    assert "insufficient evidence" in body["final_answer"].lower() or \
        "agent execution error" in body["final_answer"].lower()
    assert body["steps_used"] <= 4
