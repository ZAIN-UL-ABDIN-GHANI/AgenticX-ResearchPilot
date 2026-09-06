"""
Unit tests for the three research tools in isolation:
web_search, fetch_page, summarize.

Network calls are monkeypatched at the lowest internal method
(``_search``/``_fetch``/``_call_gemini``) so these tests never touch the
network and run deterministically offline.
"""

import httpx
import pytest

from app.tools.web_search import WebSearchTool
from app.tools.fetch_page import FetchPageTool
from app.tools.summarize import SummarizationTool
from app.schemas.tools import SearchResult


# ---------------------------------------------------------------------------
# Web Search Tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_web_search_success(monkeypatch):
    tool = WebSearchTool(api_key="k", search_engine_id="e")

    async def fake_search(self, query, max_results):
        return [
            SearchResult(
                source_id="SRC-001",
                title="Result",
                url="https://example.com",
                snippet="snippet",
                domain="example.com",
            )
        ]

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    result = await tool.execute("test query", max_results=5)

    assert result.success is True
    assert result.result_count == 1
    assert result.results[0].source_id == "SRC-001"


@pytest.mark.asyncio
async def test_web_search_empty_results(monkeypatch):
    tool = WebSearchTool(api_key="k", search_engine_id="e")

    async def fake_search(self, query, max_results):
        return []

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    result = await tool.execute("obscure query", max_results=5)

    assert result.success is True
    assert result.result_count == 0
    assert result.results == []


@pytest.mark.asyncio
async def test_web_search_timeout(monkeypatch):
    tool = WebSearchTool(api_key="k", search_engine_id="e")

    async def fake_search(self, query, max_results):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    result = await tool.execute("query", max_results=5)

    assert result.success is False
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_web_search_api_failure(monkeypatch):
    tool = WebSearchTool(api_key="k", search_engine_id="e")

    async def fake_search(self, query, max_results):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        raise httpx.HTTPStatusError("server error", request=request, response=response)

    monkeypatch.setattr(WebSearchTool, "_search", fake_search)
    result = await tool.execute("query", max_results=5)

    assert result.success is False
    assert result.error == "API error"


# ---------------------------------------------------------------------------
# Fetch Page Tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_page_success(monkeypatch):
    tool = FetchPageTool(timeout=15, user_agent="test-agent")

    async def fake_fetch(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            request=request,
            text="<html><head><title>Hi</title></head><body>Hello world</body></html>",
        )

    monkeypatch.setattr(FetchPageTool, "_fetch", fake_fetch)
    result = await tool.execute(url="https://example.com", source_id="SRC-001")

    assert result.success is True
    assert result.fetch_status == "success"
    assert "Hello world" in result.content
    assert result.title == "Hi"


@pytest.mark.asyncio
async def test_fetch_page_blocks_unsafe_url():
    tool = FetchPageTool(timeout=15, user_agent="test-agent")

    result = await tool.execute(url="http://127.0.0.1/admin", source_id="SRC-001")

    assert result.success is False
    assert result.fetch_status == "forbidden"


@pytest.mark.asyncio
async def test_fetch_page_not_found(monkeypatch):
    tool = FetchPageTool(timeout=15, user_agent="test-agent")

    async def fake_fetch(self, url):
        request = httpx.Request("GET", url)
        return httpx.Response(404, request=request, text="")

    monkeypatch.setattr(FetchPageTool, "_fetch", fake_fetch)
    result = await tool.execute(url="https://example.com/missing", source_id="SRC-002")

    assert result.success is False
    assert result.fetch_status == "error"


@pytest.mark.asyncio
async def test_fetch_page_timeout(monkeypatch):
    tool = FetchPageTool(timeout=15, user_agent="test-agent")

    async def fake_fetch(self, url):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(FetchPageTool, "_fetch", fake_fetch)
    result = await tool.execute(url="https://example.com/slow", source_id="SRC-003")

    assert result.success is False
    assert result.fetch_status == "timeout"


@pytest.mark.asyncio
async def test_fetch_page_invalid_url_rejected():
    tool = FetchPageTool(timeout=15, user_agent="test-agent")

    # Non-http(s) URLs must be rejected by request validation without any
    # network call, but as a graceful failure result -- not an exception --
    # matching the "never crash on bad input" failure-handling policy.
    result = await tool.execute(url="ftp://example.com/file", source_id="SRC-004")

    assert result.success is False


# ---------------------------------------------------------------------------
# Summarization Tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_success(monkeypatch):
    tool = SummarizationTool(api_key="k")

    async def fake_call(self, prompt):
        return (
            '{"summary": "A short summary.", "key_claims": '
            '[{"claim": "X is Y", "evidence": "because Z", "confidence": 0.8}]}'
        )

    monkeypatch.setattr(SummarizationTool, "_call_gemini", fake_call)
    result = await tool.execute(
        source_id="SRC-001", content="x" * 200, context="What is X?"
    )

    assert result.success is True
    assert result.summary == "A short summary."
    assert len(result.key_claims) == 1
    assert result.key_claims[0].claim == "X is Y"


@pytest.mark.asyncio
async def test_summarize_malformed_response(monkeypatch):
    tool = SummarizationTool(api_key="k")

    async def fake_call(self, prompt):
        return "this is not valid json at all"

    monkeypatch.setattr(SummarizationTool, "_call_gemini", fake_call)
    result = await tool.execute(source_id="SRC-001", content="x" * 200)

    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_summarize_gemini_failure(monkeypatch):
    tool = SummarizationTool(api_key="k")

    async def fake_call(self, prompt):
        raise RuntimeError("Gemini API unavailable")

    monkeypatch.setattr(SummarizationTool, "_call_gemini", fake_call)
    result = await tool.execute(source_id="SRC-001", content="x" * 200)

    assert result.success is False
    assert result.error == "Summarization failed"
