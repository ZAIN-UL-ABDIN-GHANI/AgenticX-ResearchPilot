# ResearchPilot AI — API Documentation

Base URL (local dev): `http://localhost:8000`
All endpoints are versioned under `/api/v1` except `/health`.
Interactive docs (Swagger UI): `GET /docs` · OpenAPI schema: `GET /openapi.json`

---

## Authentication

None in this deliverable — the API is unauthenticated, matching the
project's stated scope. See `docs/SYSTEM_DESIGN.md` §3 (non-goals) and add
an auth layer (e.g. an API-key dependency on the router) before exposing
this publicly.

---

## `GET /health`

Liveness check for orchestrators/load balancers. Always fast, no DB access.

**Response `200`**
```json
{ "status": "healthy", "version": "1.0.0", "environment": null }
```

---

## `GET /`

API root / metadata.

**Response `200`**
```json
{ "name": "ResearchPilot AI", "version": "1.0.0", "docs": "/docs" }
```

---

## `POST /api/v1/research`

Start a new research run. Creates the run record and returns immediately;
the LangGraph agent executes afterward as a background task.

**Request body**
```json
{
  "question": "What is RAG and why is it useful for LLM applications?",
  "max_steps": 8
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | yes | 1–500 characters after trimming. Blank/whitespace-only is rejected. |
| `max_steps` | integer | no | Defaults to the server's `MAX_STEPS` setting (8). Hard upper bound enforced by the agent regardless of this value's size. |

**Response `201 Created`**
```json
{
  "research_id": "1",
  "question": "What is RAG and why is it useful for LLM applications?",
  "status": "running",
  "max_steps": 8,
  "created_at": "2026-09-04T03:41:34.223350"
}
```

**Errors**
| Status | Cause |
|---|---|
| `400` | Question is empty/whitespace-only after trimming. |
| `422` | Question exceeds 500 characters, or the body fails schema validation (Pydantic). |

---

## `GET /api/v1/research/{research_id}`

Poll the status of a research run. Call this on an interval (the frontend
polls every few seconds) until `status` is terminal.

**Response `200`**
```json
{
  "research_id": "1",
  "question": "What is RAG and why is it useful for LLM applications?",
  "status": "completed",
  "max_steps": 8,
  "steps_used": 5,
  "final_answer": "Retrieval-Augmented Generation (RAG) grounds language model answers in retrieved documents... [1][2]\n\n## Sources\n[1] RAG Explained — https://example.com/rag\n[2] ...",
  "created_at": "2026-09-04T03:41:34.223350",
  "completed_at": "2026-09-04T03:41:39.442930"
}
```

`status` is one of: `running`, `completed`, `failed`, `step_limit_reached`.
`final_answer` is `null` while `status` is `running`. On `failed`, it
contains an honest message (e.g. *"Insufficient evidence was gathered to
produce a supported answer within the step budget."*) rather than a
fabricated answer.

**Errors**
| Status | Cause |
|---|---|
| `404` | No research run with that id. |

---

## `GET /api/v1/research/{research_id}/sources`

All sources discovered during the run, whether or not they were
successfully fetched.

**Response `200`**
```json
{
  "sources": [
    {
      "source_id": "SRC-001",
      "url": "https://example.com/rag",
      "title": "RAG Explained",
      "domain": "example.com",
      "fetch_status": "success",
      "word_count": 240,
      "fetched_at": "2026-09-04T03:41:35.100000"
    }
  ]
}
```

`fetch_status` is one of: `pending`, `success`, `error`, `timeout`,
`forbidden` (blocked by SSRF validation). A source is only ever eligible for
citation when `fetch_status == "success"`.

---

## `GET /api/v1/research/{research_id}/tools`

The full, chronological tool-call trace for the run — this is what powers
the frontend's live timeline.

**Response `200`**
```json
{
  "tool_calls": [
    {
      "step_number": 1,
      "tool_name": "web_search",
      "status": "success",
      "input": { "query": "What is RAG?", "max_results": 5 },
      "output": { "success": true, "result_count": 1 },
      "created_at": "2026-09-04T03:41:34.284000"
    },
    {
      "step_number": 2,
      "tool_name": "fetch_page",
      "status": "success",
      "input": { "url": "https://example.com/rag", "source_id": "SRC-001" },
      "output": { "success": true, "fetch_status": "success" },
      "created_at": "2026-09-04T03:41:34.900000"
    },
    {
      "step_number": 3,
      "tool_name": "summarize",
      "status": "success",
      "input": { "source_id": "SRC-001" },
      "output": { "success": true },
      "created_at": "2026-09-04T03:41:35.400000"
    }
  ]
}
```

---

## `GET /api/v1/research/{research_id}/claims`

Every claim in the final answer that passed citation validation, with its
full citation chain.

**Response `200`**
```json
{
  "claims": [
    {
      "claim_id": 1,
      "claim_text": "RAG grounds answers in retrieved documents",
      "citations": [
        {
          "source_id": "SRC-001",
          "url": "https://example.com/rag",
          "title": "RAG Explained",
          "citation_number": 1,
          "confidence": 90,
          "evidence": "Retrieval-Augmented Generation (RAG) grounds language model answers in retrieved documents..."
        }
      ]
    }
  ]
}
```

`confidence` is an integer percentage (0–100), derived from the tool's
`0.0–1.0` confidence score. A claim with an empty `citations` array should
never appear in this list — **NO SOURCE = NO CLAIM** is enforced before
persistence (see `docs/BACKEND_DOCUMENTATION.md` §15).

---

## Typical client flow

```
1. POST /api/v1/research           -> 201, { research_id }
2. loop:
     GET /api/v1/research/{id}          -> check status
     GET /api/v1/research/{id}/sources
     GET /api/v1/research/{id}/tools
     GET /api/v1/research/{id}/claims
     until status in {completed, failed, step_limit_reached}
3. Render final_answer + claims/citations
```

This is exactly what `frontend/src/hooks/useResearchAPI.ts`'s
`pollResearch()` implements.
