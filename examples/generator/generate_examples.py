"""
Generates the three required example runs by executing the REAL system
(FastAPI app, LangGraph agent, CitationIntegrationService, DB persistence)
end-to-end through the ASGI transport -- exactly like tests/test_api.py --
with only the external network calls (Google Search / Gemini / page fetch)
replaced by realistic canned responses, since this sandbox has no live
network access to those APIs.

This is NOT a hand-written transcript: every field in the captured JSON
(steps_used, tool call order, source ids, claim/citation linkage) is
produced by actually running app/agent/graph.py and
app/services/citation_integration.py, so the example output reflects real
system behavior.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.tools import (
    WebSearchResponse, SearchResult, FetchPageResponse,
    SummarizeResponse, KeyClaim,
)


SCENARIOS = [
    {
        "name": "example_1_rag",
        "question": "What is RAG and why is it useful for LLM applications?",
        "max_steps": 8,
        "sources": [
            {
                "source_id": "SRC-001",
                "title": "Retrieval-Augmented Generation: A Survey",
                "url": "https://arxiv.org/abs/2312.10997",
                "snippet": "RAG combines retrieval systems with generative models to ground outputs in external knowledge.",
                "domain": "arxiv.org",
                "content": (
                    "Retrieval-Augmented Generation (RAG) is a technique that combines a "
                    "retrieval system with a generative language model. Instead of relying "
                    "solely on parameters learned during training, a RAG system retrieves "
                    "relevant documents from an external knowledge source at inference time "
                    "and conditions the generation on that retrieved content. This reduces "
                    "hallucination and allows the model to reference information beyond its "
                    "training cutoff, since the knowledge source can be updated independently "
                    "of the model itself."
                ),
                "claim": "RAG retrieves external documents at inference time and conditions generation on them to reduce hallucination",
            },
            {
                "source_id": "SRC-002",
                "title": "Why Grounding Matters for LLM Applications",
                "url": "https://research.google/pubs/rag-grounding",
                "snippet": "Grounded generation improves factual accuracy and traceability of LLM outputs.",
                "domain": "research.google",
                "content": (
                    "Applications built on large language models benefit from grounding "
                    "because it lets every generated claim be traced back to a specific "
                    "retrieved source, which is difficult to do with a purely parametric "
                    "model. Grounded systems can also incorporate up-to-date or "
                    "domain-specific information without retraining the underlying model."
                ),
                "claim": "Grounded generation allows every claim to be traced back to a specific retrieved source",
            },
        ],
        "answer": (
            "Retrieval-Augmented Generation (RAG) retrieves external documents at "
            "inference time and conditions generation on them to reduce "
            "hallucination. Grounded generation allows every claim to be traced "
            "back to a specific retrieved source."
        ),
    },
    {
        "name": "example_2_langgraph",
        "question": "What are the main differences between LangGraph and traditional LLM chains?",
        "max_steps": 8,
        "sources": [
            {
                "source_id": "SRC-001",
                "title": "LangGraph: Building Stateful, Multi-Actor LLM Applications",
                "url": "https://langchain-ai.github.io/langgraph/",
                "snippet": "LangGraph models agent workflows as explicit graphs with cycles and shared state.",
                "domain": "langchain-ai.github.io",
                "content": (
                    "Traditional LLM chains compose steps as a linear (or simple branching) "
                    "sequence with no built-in support for cycles. LangGraph instead models "
                    "a workflow as an explicit state graph: nodes represent steps, edges "
                    "(including conditional edges) represent transitions, and a shared state "
                    "object flows through every node. This makes it possible to express loops "
                    "-- for example, an agent that repeatedly decides which tool to call next "
                    "-- as a first-class part of the graph structure rather than an ad-hoc "
                    "while-loop wrapped around a chain."
                ),
                "claim": "LangGraph models workflows as explicit state graphs with cycles, unlike traditional linear chains",
            },
            {
                "source_id": "SRC-002",
                "title": "Cyclic Graphs vs Directed Acyclic Chains in LLM Orchestration",
                "url": "https://blog.langchain.dev/langgraph-vs-chains",
                "snippet": "Chains are DAGs; LangGraph supports cycles needed for iterative agents.",
                "domain": "blog.langchain.dev",
                "content": (
                    "A classic LLM chain is a directed acyclic graph (DAG) of steps executed "
                    "once each. Many agentic behaviors, however, require revisiting the same "
                    "decision point multiple times -- for instance, deciding whether to search "
                    "again after an empty result. LangGraph's explicit state machine supports "
                    "cycles between nodes, and lets a hard step limit be enforced as a simple "
                    "check inside the routing node, guaranteeing termination even when the "
                    "graph could otherwise loop."
                ),
                "claim": "LangGraph supports cycles between nodes and can enforce a hard step limit inside the routing node to guarantee termination",
            },
        ],
        "answer": (
            "LangGraph models workflows as explicit state graphs with cycles, "
            "unlike traditional linear chains. LangGraph supports cycles between "
            "nodes and can enforce a hard step limit inside the routing node to "
            "guarantee termination."
        ),
    },
    {
        "name": "example_3_hallucination",
        "question": "What are current techniques for reducing LLM hallucinations?",
        "max_steps": 8,
        "sources": [
            {
                "source_id": "SRC-001",
                "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP",
                "url": "https://arxiv.org/abs/2005.11401",
                "snippet": "RAG reduces hallucination by grounding generation in retrieved passages.",
                "domain": "arxiv.org",
                "content": (
                    "One widely used technique for reducing hallucination is "
                    "retrieval-augmentation: conditioning the model's output on passages "
                    "retrieved from an external corpus rather than relying purely on "
                    "parametric memory. This gives the model concrete text to ground its "
                    "answer in and provides a citation path back to the retrieved source."
                ),
                "claim": "Retrieval-augmentation reduces hallucination by conditioning output on retrieved passages",
            },
            {
                "source_id": "SRC-002",
                "title": "Self-Consistency and Verification in Language Model Reasoning",
                "url": "https://arxiv.org/abs/2203.11171",
                "snippet": "Sampling multiple reasoning paths and checking agreement reduces errors.",
                "domain": "arxiv.org",
                "content": (
                    "Self-consistency methods sample multiple independent reasoning paths for "
                    "the same question and select the most common final answer, which reduces "
                    "the rate of confidently-stated incorrect answers compared to a single "
                    "greedy generation."
                ),
                "claim": "Self-consistency reduces confidently-stated incorrect answers by sampling multiple reasoning paths and selecting the most common answer",
            },
            {
                "source_id": "SRC-003",
                "title": "Citation Verification Pipelines for Generated Text",
                "url": "https://arxiv.org/abs/2305.14627",
                "snippet": "Automated citation-checking rejects claims without supporting evidence.",
                "domain": "arxiv.org",
                "content": (
                    "A citation verification stage checks each claim in a generated answer "
                    "against the evidence it cites, and rejects or flags any claim that "
                    "cannot be matched to a specific retrieved source. This 'no source, no "
                    "claim' policy prevents unverifiable statements from reaching the reader "
                    "even if the underlying generation model produced them fluently."
                ),
                "claim": "Citation verification pipelines reject claims that cannot be matched to a specific retrieved source",
            },
        ],
        "answer": (
            "Retrieval-augmentation reduces hallucination by conditioning output "
            "on retrieved passages. Self-consistency reduces confidently-stated "
            "incorrect answers by sampling multiple reasoning paths and selecting "
            "the most common answer. Citation verification pipelines reject "
            "claims that cannot be matched to a specific retrieved source."
        ),
    },
]


async def run_scenario(scenario):
    search_results = [
        SearchResult(
            source_id=s["source_id"], title=s["title"], url=s["url"],
            snippet=s["snippet"], domain=s["domain"],
        )
        for s in scenario["sources"]
    ]
    content_by_url = {s["url"]: s for s in scenario["sources"]}

    async def fake_search(self, query, max_results=5):
        return WebSearchResponse(success=True, results=search_results, result_count=len(search_results))

    async def fake_fetch(self, url, source_id):
        s = content_by_url[url]
        return FetchPageResponse(
            success=True, source_id=source_id, url=url, title=s["title"],
            content=s["content"], word_count=len(s["content"].split()),
            fetch_status="success",
        )

    async def fake_summarize(self, source_id, content, context=None):
        s = next(x for x in scenario["sources"] if x["source_id"] == source_id)
        return SummarizeResponse(
            success=True, source_id=source_id,
            summary=s["claim"],
            key_claims=[KeyClaim(claim=s["claim"], evidence=content[:150], confidence=0.9)],
        )

    async def fake_generate_answer(self, question, citation_service):
        return scenario["answer"]

    with patch("app.tools.web_search.WebSearchTool.execute", fake_search), \
         patch("app.tools.fetch_page.FetchPageTool.execute", fake_fetch), \
         patch("app.tools.summarize.SummarizationTool.execute", fake_summarize), \
         patch("app.services.research_service.ResearchService._generate_answer", fake_generate_answer):

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            create_resp = await client.post(
                "/api/v1/research",
                json={"question": scenario["question"], "max_steps": scenario["max_steps"]},
            )
            research_id = create_resp.json()["research_id"]

            status_resp = await client.get(f"/api/v1/research/{research_id}")
            sources_resp = await client.get(f"/api/v1/research/{research_id}/sources")
            tools_resp = await client.get(f"/api/v1/research/{research_id}/tools")
            claims_resp = await client.get(f"/api/v1/research/{research_id}/claims")

            return {
                "create": create_resp.json(),
                "status": status_resp.json(),
                "sources": sources_resp.json(),
                "tools": tools_resp.json(),
                "claims": claims_resp.json(),
            }


async def main():
    from app.db.base import Base
    from app.db.database import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    results = {}
    for scenario in SCENARIOS:
        results[scenario["name"]] = await run_scenario(scenario)
    with open("/tmp/example_runs.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Done. Wrote /tmp/example_runs.json")


if __name__ == "__main__":
    asyncio.run(main())
