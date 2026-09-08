# Example 1 — What is RAG and why is it useful for LLM applications?

> **Note on how this example was produced:** this is real output from the actual system (`POST /api/v1/research` -> the real LangGraph agent -> the real citation validator -> the real database), captured via `backend/generate_examples.py`. Because this sandboxed environment has no live network access to the Google Search/Gemini APIs, the network calls made by the three tools (`web_search`, `fetch_page`, `summarize`) were substituted with realistic, fixed responses so the example is reproducible -- everything downstream of those calls (agent routing, step counting, citation validation, database persistence, and the API responses below) is the real, unmodified system.

## Request

```http
POST /api/v1/research
Content-Type: application/json

{
  "question": "What is RAG and why is it useful for LLM applications?",
  "max_steps": 8
}
```

## Agent Execution Trace

**Steps used:** 6 / 8   |   **Final status:** `completed`

| Step | Tool | Status | Detail |
|---|---|---|---|
| 1 | `web_search` | success | query: "What is RAG and why is it useful for LLM applications?" → 2 result(s) |
| 2 | `fetch_page` | success | SRC-001: 73 words fetched |
| 3 | `fetch_page` | success | SRC-002: 47 words fetched |
| 4 | `summarize` | success | SRC-001: "RAG retrieves external documents at inference time and conditions generation on them to reduce hallucination" |
| 5 | `summarize` | success | SRC-002: "Grounded generation allows every claim to be traced back to a specific retrieved source" |

## Sources Discovered

| Source ID | Title | Domain | Fetch Status | Words |
|---|---|---|---|---|
| SRC-001 | Retrieval-Augmented Generation: A Survey | arxiv.org | success | 73 |
| SRC-002 | Why Grounding Matters for LLM Applications | research.google | success | 47 |

## Claims and Citations

**Claim 1:** Retrieval-Augmented Generation (RAG) retrieves external documents at inference time and conditions generation on them to reduce hallucination.

- **[1]** Retrieval-Augmented Generation: A Survey — https://arxiv.org/abs/2312.10997 (confidence: 90%)
  > _Evidence:_ "Retrieval-Augmented Generation (RAG) is a technique that combines a retrieval system with a generative language model. Instead of relying solely on pa"

**Claim 2:** Grounded generation allows every claim to be traced back to a specific retrieved source.

- **[2]** Why Grounding Matters for LLM Applications — https://research.google/pubs/rag-grounding (confidence: 90%)
  > _Evidence:_ "Applications built on large language models benefit from grounding because it lets every generated claim be traced back to a specific retrieved source"

## Final Answer (as returned by `GET /api/v1/research/{id}`)

```
Retrieval-Augmented Generation (RAG) retrieves external documents at inference time and conditions generation on them to reduce hallucination [1] Grounded generation allows every claim to be traced back to a specific retrieved source [2]

## Sources

[1] Retrieval-Augmented Generation: A Survey
    Domain: arxiv.org
    URL: https://arxiv.org/abs/2312.10997

[2] Why Grounding Matters for LLM Applications
    Domain: research.google
    URL: https://research.google/pubs/rag-grounding


```

## What This Demonstrates

- The agent selected `web_search` first, then `fetch_page` for each discovered source, then `summarize` for each successfully fetched source, before finishing -- exactly the planner routing logic described in `docs/SYSTEM_DESIGN.md` §8.
- Both claims in the final answer trace to a distinct fetched source (SRC-001, SRC-002), each with a citation number matching the `[1]`/`[2]` markers in the answer text.
