# ResearchPilot AI — Backend Technical Documentation

**Stack:** Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.x · PostgreSQL · Alembic · LangChain · LangGraph · Google Gemini

---

## Table of Contents

1. [Backend Overview](#1-backend-overview)
2. [Why FastAPI](#2-why-fastapi)
3. [Why Python](#3-why-python)
4. [Why Pydantic](#4-why-pydantic)
5. [Why SQLAlchemy](#5-why-sqlalchemy)
6. [Why PostgreSQL](#6-why-postgresql)
7. [Why Alembic](#7-why-alembic)
8. [Why LangChain](#8-why-langchain)
9. [Why LangGraph](#9-why-langgraph)
10. [Why Gemini](#10-why-gemini)
11. [Agent Architecture](#11-agent-architecture)
12. [State Management](#12-state-management)
13. [Tool Architecture](#13-tool-architecture)
14. [RAG Pipeline](#14-rag-pipeline)
15. [Citation Architecture](#15-citation-architecture)
16. [Database Architecture](#16-database-architecture)
17. [API Architecture](#17-api-architecture)
18. [Repository/Service Architecture](#18-repositoryservice-architecture)
19. [Error Handling](#19-error-handling)
20. [Security](#20-security)
21. [Testing](#21-testing)
22. [Docker](#22-docker)
23. [Environment Configuration](#23-environment-configuration)
24. [Production Deployment](#24-production-deployment)
25. [Complete Backend Summary](#25-complete-backend-summary)
26. [What Was Used and Why](#26-what-was-used-and-why)

---

## 1. Backend Overview

The backend is a FastAPI application whose central responsibility is
running a LangGraph-orchestrated research agent and persisting every
artifact it produces. It is organized in strict layers (API → Services →
Agent → Tools / Repositories → Database) so that the agent's control flow,
the tools it calls, and the database it writes to can each be tested in
isolation. Six REST endpoints expose the full lifecycle: start a research
run, and read back its status, sources, tool calls, and claims.

## 2. Why FastAPI

Async-native (the entire I/O path — HTTP calls to Gemini/Search/target
pages, and database access via SQLAlchemy's async engine — is `async`/`await`
throughout, so a slow fetch or LLM call never blocks the event loop),
automatic OpenAPI schema generation (used directly for the API
documentation in this deliverable — see `docs/API_DOCUMENTATION.md`), and
first-class Pydantic integration for request/response validation. Its
`BackgroundTasks` mechanism is what lets `POST /api/v1/research` return in
milliseconds while the actual multi-step agent run happens after the
response is sent (§17).

## 3. Why Python

The entire AI/agent ecosystem this project depends on — LangChain,
LangGraph, the Google Generative AI SDK — is Python-first, and Python's
`async`/`await` model maps directly onto FastAPI's. Type hints throughout
the codebase (every function signature, every Pydantic model) give the same
compile-adjacent safety TypeScript gives the frontend, checked via `mypy` in
CI.

## 4. Why Pydantic

Two distinct jobs, both handled by Pydantic v2: **settings** (`Settings` in
`app/core/config.py`, a `BaseSettings` subclass that loads and validates
every environment variable once at import time — a malformed `MAX_STEPS` or
missing required field fails fast at startup, not mid-request) and **I/O
schemas** (`app/schemas/`) for both the public API (`ResearchCreateRequest`
enforces the question length limit before a request ever reaches the
service layer) and the internal tool contracts (`WebSearchResponse`,
`FetchPageResponse`, `SummarizeResponse` — every tool's output is a typed,
validated model, not a loose dict).

## 5. Why SQLAlchemy

SQLAlchemy 2.x's async engine/session (`create_async_engine`,
`AsyncSession`) is the natural fit for an all-async FastAPI app, and its
declarative ORM models (`app/db/models.py`) express the five-table schema
(research_runs, sources, tool_calls, claims, claim_sources) with real
foreign keys and relationships, letting repositories use `selectinload` for
eager-loaded, N+1-free queries (used in `ClaimRepository.get_by_research` to
fetch a claim's citations and their source in one query — see §19 for the
lazy-load bug this specifically fixed).

## 6. Why PostgreSQL

Production requirement per project scope, and a good fit regardless: the
schema is fully relational (five tables joined by foreign keys, no
document-shaped or schema-flexible data anywhere), and PostgreSQL's JSON
column type is used for `tool_calls.input`/`.output`, so a tool's exact
request/response payload is queryable without a separate document store.
SQLite (via `aiosqlite`) is used only as a zero-setup substitute for local
development and the test suite — the schema, migrations, and application
code are identical either way; only `DATABASE_URL` changes.

## 7. Why Alembic

Alembic gives the schema a versioned, reviewable migration history
(`backend/alembic/versions/001_initial_schema.py`) instead of relying on
`create_all` in production, and supports both `upgrade` and `downgrade` —
verified directly in this phase (`alembic upgrade head` then
`alembic downgrade base` cleanly creates and then drops all five tables).
Because Alembic runs synchronously while the app itself is fully async,
`alembic/env.py` swaps the configured `DATABASE_URL`'s async driver for its
sync equivalent purely for the migration run (§19 — this is one of the real
bugs found and fixed in this phase).

## 8. Why LangChain

LangChain supplies the Gemini chat-model integration surface and message/
tool-schema conventions that LangGraph is built on top of; using it (rather
than hand-rolling a Gemini HTTP client) keeps the agent layer aligned with
the broader LangGraph ecosystem's conventions for future extension (e.g.
swapping in LangChain's own tool-calling abstractions later without
restructuring the graph).

## 9. Why LangGraph

This is the project's central agentic-architecture requirement: **a real
state graph, not a while-loop.** LangGraph's `StateGraph` makes the agent's
control flow an explicit, declared structure — nodes (`planner`, `search`,
`fetch`, `summarize`) and edges (including the conditional edges out of
`planner`) — which is both what the spec requires and what makes the hard
step limit testable as an isolated property of the graph
(`test_hard_step_limit_guarantees_termination` in §21) rather than something
that has to be inferred from reading loop logic. See
`docs/SYSTEM_DESIGN.md` §7–8 for the full graph design.

## 10. Why Gemini

Per project constraint, Gemini is the only LLM provider — no other provider
is implemented or configurable. It's used for two structured tasks
(evidence extraction in `SummarizationTool`, final-answer synthesis in
`ResearchService._generate_answer`), both isolated behind a single call site
each so the integration surface stays small (§26 in `docs/SYSTEM_DESIGN.md`
§12 covers the architecture in more depth).

## 11. Agent Architecture

```
app/agent/
├── state.py    ResearchState (TypedDict) + initial_state() builder
└── graph.py    AgentContext, build_research_graph() -> compiled StateGraph
```

`build_research_graph(ctx: AgentContext)` returns a graph compiled fresh for
each research run (so no state leaks between runs), with `ctx` supplying the
repositories and `CitationIntegrationService` instance the node closures
need. See `docs/SYSTEM_DESIGN.md` §7–9 for the node-by-node design and the
planner's routing logic — this document focuses on how it's tested rather
than re-deriving the design.

## 12. State Management

`ResearchState` is a `TypedDict` — plain, JSON-serializable data only
(question, `step_count`, `queries_tried`, `search_results`, `fetched`,
`summarized`, `tool_errors`, `next_action`, `status`). Nothing
non-serializable (a DB session, a tool instance) is ever put into this
state; those live in `AgentContext` and are closed over by the node
functions instead. This split is what makes `tests/test_agent_graph.py`
possible: a test can build a real `AgentContext` against a real (in-memory
SQLite) session, monkeypatch only the tool `.execute()` methods, and invoke
the actual compiled graph — no separate "test mode" code path exists in the
graph itself.

## 13. Tool Architecture

```
app/tools/
├── web_search.py   WebSearchTool  -> WebSearchResponse
├── fetch_page.py   FetchPageTool  -> FetchPageResponse
└── summarize.py    SummarizationTool -> SummarizeResponse
```

Every tool follows the same shape: an `async execute(...)` method that never
raises — internal `try`/`except` blocks convert every failure mode (HTTP
error, timeout, malformed response, SSRF block) into a `success=False`
response with a populated `error`/`fetch_status` field, so the agent graph
never needs a `try`/`except` around a tool call. This is what "no fake
tools" means concretely in this codebase: each tool makes a real network
call (Google Custom Search API, `httpx` GET to the target page, Gemini
`generate_content`) and its failure paths are real failure paths, not
placeholders — see `docs/SYSTEM_DESIGN.md` §9 for behavior details and §21
for the full test matrix.

## 14. RAG Pipeline

See `docs/SYSTEM_DESIGN.md` §10 for the full pipeline and the reasoning
against adding a vector database. In backend terms: `fetch_page` output
feeds `summarize`, whose `key_claims`/`evidence` feed
`CitationIntegrationService.add_evidence_from_summary`, building the
in-memory `evidence_map` that `ResearchService._generate_answer` uses as the
*only* source of truth for the Gemini synthesis prompt.

## 15. Citation Architecture

```
app/services/citation_integration.py   CitationIntegrationService
app/repositories/claim_repository.py   ClaimRepository
```

`CitationIntegrationService` tracks sources (`sources_map`) and evidence
(`evidence_map`) as they're discovered/fetched/summarized, then
`validate_answer(text)` splits a generated answer into claim-like sentences
and matches each against the evidence map, producing a report with
`verified`/`unverified` claims and their supporting `source_ids`/
`evidence_ids`. `ResearchService._persist_claims` consumes that report and
is the *only* code path that writes to `claims`/`claim_sources` — and it
re-validates `source.fetch_status == "success"` before writing a citation
even for claims the validator already marked verified, so **NO SOURCE = NO
CLAIM** holds even if the validator's sentence-matching heuristic were ever
wrong in the permissive direction. `ClaimRepository.get_by_research` uses
`selectinload(Claim.claim_sources).selectinload(ClaimSource.source)` so the
`/claims` endpoint can read the whole chain in one query (§19 covers the bug
this fixed).

## 16. Database Architecture

See `docs/SYSTEM_DESIGN.md` §15 for the full ER diagram. Two backend-specific
notes:

- **Index naming** — every index name must be unique per-database (not just
  per-table) in SQLite, and both `sources` and `tool_calls` originally
  declared an index literally named `idx_research_run_id`, which crashed
  table creation entirely. Fixed by giving each table's index a
  table-qualified name (`idx_sources_research_run_id`,
  `idx_tool_calls_research_run_id`) in both the ORM models and the Alembic
  migration, so `Base.metadata.create_all` (dev) and `alembic upgrade head`
  (production) produce an identical schema.
- **Connection pooling** — `database.py` only applies `pool_size`/
  `max_overflow`/`pool_pre_ping` when the URL is PostgreSQL; SQLite instead
  gets `StaticPool` + `check_same_thread=False`, which is what lets an
  in-memory SQLite database persist across every request/test within one
  process (there is effectively one physical connection, reused).

## 17. API Architecture

```
POST   /api/v1/research                     -> 201, {research_id, status: "running", ...}
GET    /api/v1/research/{id}                -> run status + final_answer (if terminal)
GET    /api/v1/research/{id}/sources         -> all discovered sources + fetch_status
GET    /api/v1/research/{id}/tools           -> chronological tool_calls
GET    /api/v1/research/{id}/claims          -> claims with full citation chains
GET    /health                                -> liveness for Docker/orchestrators
```

`POST /api/v1/research` is the one endpoint with a side effect beyond the
database write: after committing the new `research_runs` row, it schedules
`ResearchService().run_research(...)` via FastAPI's `BackgroundTasks`, so
the HTTP response completes immediately while the agent keeps running in
the same process. This was in fact the central gap found in this codebase
during this phase — the route imported `ResearchService` but never called
it, so research runs were created and then simply never executed. Wiring
this call is what makes the API's `GET` endpoints meaningful at all (§19).

## 18. Repository/Service Architecture

Repositories (`research_`, `source_`, `tool_call_`, `claim_repository.py`)
are the *only* layer that imports SQLAlchemy models directly — every other
layer works through them. `ResearchService` (the orchestration layer) and
`CitationIntegrationService` (the evidence/validation layer) sit between the
API and the agent: the API layer never touches the agent graph directly,
and the agent graph never touches the API layer's schemas. This means the
agent can be invoked identically from the API route (production path) or
directly from a test (`tests/test_agent_graph.py`), with the exact same
persistence behavior either way.

## 19. Error Handling

See `docs/SYSTEM_DESIGN.md` §16 for the full failure-handling matrix. Bugs
found and fixed specifically in this phase, each confirmed via a live
reproduction before and after the fix:

| Bug | Symptom | Fix |
|---|---|---|
| Missing `app/services/research_service.py` | `POST /research` created a DB row and did nothing else — the agent never ran | Implemented the service; wired it into the route via `BackgroundTasks` |
| Missing `app/agent/` package | No real LangGraph graph existed anywhere in the codebase (only a non-integrated, simulated Phase 4-6 prototype) | Implemented `state.py`/`graph.py` per §11 |
| Missing `app/repositories/claim_repository.py` | Referenced nowhere, claims had no dedicated eager-loaded query path | Implemented per §15 |
| Duplicate SQL index name (`idx_research_run_id` on two tables) | `Base.metadata.create_all()` raised on startup — the app couldn't boot at all | Table-qualified index names in both ORM models and the Alembic migration |
| `FetchPageResponse.domain` accessed but doesn't exist on the schema | `AttributeError` on every successfully fetched source | Derive domain from the URL via `urlparse` instead |
| Alembic reused the app's async `DATABASE_URL` | `alembic upgrade head` raised `InvalidRequestError` — migrations couldn't run at all | `env.py` now swaps in the sync-driver equivalent before running migrations |
| `research.claims` accessed as a lazy relationship after the query | `GET /research/{id}/claims` raised `MissingGreenlet` under async SQLAlchemy | Route now uses `ClaimRepository.get_by_research`'s eager-loaded query |
| CI workflow's `DATABASE_URL` used the bare `postgresql://` scheme | Reproduced locally: `create_async_engine` raises `InvalidRequestError` at import time (psycopg2 is not async) | CI now uses `postgresql+asyncpg://` |

All eight were found by actually running the application (starting the
server, hitting endpoints, running `alembic upgrade`/`downgrade`, running
the reconstructed test suite) rather than by static review alone — see
`docs/TROUBLESHOOTING.md` for a version of this table aimed at someone
running the project locally.

## 20. Security

See `docs/SYSTEM_DESIGN.md` §16 for the full policy. Backend-specific
implementation notes: `Settings` reads every secret from the environment
with a clearly-fake default (`"test-key"`, `"change-me-in-production"`) so
the app is runnable out-of-the-box for local dev/tests without a real key,
while still making it obvious in `.env.example` that these must be replaced
in any real deployment. `app/middleware.py`'s exception handler is the only
place a `500` response body is constructed, guaranteeing no other code path
can leak an internal traceback to a client. `app/utils/urls.py`'s SSRF
checks run inside `FetchPageTool.execute` *before* any `httpx` call is
made, so a request to a private/loopback address never leaves the process
(with the DNS-rebinding caveat noted in the System Design doc).

## 21. Testing

**36 backend tests, all passing, zero live network calls.** Run with:

```bash
cd backend
pytest tests/ -v
```

- `tests/conftest.py` — session-scoped autouse fixture that creates the full
  schema once (via `Base.metadata.create_all` against the in-memory SQLite
  `StaticPool` engine) before any test runs; without this, the three
  DB-touching tests in the pre-existing suite failed with
  `no such table: research_runs`, which was the very first bug this phase
  found and fixed.
- `tests/test_tools.py` — 13 tests: each tool's success, empty/malformed
  response, timeout, and API-failure paths, plus the SSRF-block and
  invalid-URL cases for `fetch_page`.
- `tests/test_agent_graph.py` — 4 tests: correct first-tool selection, a
  full search→fetch→summarize→finish happy path verified against both the
  returned state and the persisted `tool_calls` rows, the hard step-limit
  termination guarantee (with `recursion_limit` set generously above
  `max_steps` specifically so a broken limit would manifest as a returned-
  but-wrong state rather than a masked `GraphRecursionError`), and
  search-failure recovery via query reformulation.
- `tests/test_api.py` — 6 tests: health, empty-question validation,
  over-length validation, 404 on an unknown run, a full HTTP-level workflow
  (create → background agent execution → poll → verify sources/tool-calls/
  claims/citations all correct, including that every returned citation's
  `source_id`/`url` matches the one fetched source), and a failing-search
  run correctly reporting `status: "failed"` with an honest message.
- Plus 13 pre-existing tests (config, models, repositories, utils, basic
  tool construction) inherited from the original codebase, now passing
  under the schema fixture.

## 22. Docker

`backend/Dockerfile`: `python:3.11-slim`, system deps for `psycopg2`/health
checks, a non-root `appuser`, `pip install -r requirements.txt`, a container
`HEALTHCHECK` against `/health`. In `docker-compose.yml`, the backend
service's `command` runs `alembic upgrade head && uvicorn ... --reload`
before serving, and `depends_on: postgres: condition: service_healthy`
ensures migrations only run once Postgres is actually accepting
connections.

## 23. Environment Configuration

Every setting lives in `Settings` (`app/core/config.py`), loaded from `.env`
(and `.env.test` if present, for a dedicated test-environment override) via
Pydantic Settings, case-insensitively matched to environment variable names.
`.env.example` at the project root documents every variable across five
groups: FastAPI (`DEBUG`, `LOG_LEVEL`, `SECRET_KEY`), Database
(`DATABASE_URL` and pool sizing), Gemini (`GEMINI_API_KEY`/`_MODEL`/
`_TIMEOUT`/`_MAX_RETRIES`), Search (`SEARCH_API_KEY`/`SEARCH_ENGINE_ID`/
`_TIMEOUT`/`_MAX_RESULTS`), Agent (`MAX_STEPS`, `RESEARCH_TIMEOUT`), Web
Scraping (`FETCH_TIMEOUT`, `USER_AGENT`), Logging, CORS
(`ALLOWED_ORIGINS`), Rate Limiting, and the frontend's
`NEXT_PUBLIC_API_URL`.

## 24. Production Deployment

1. Provision PostgreSQL and set `DATABASE_URL=postgresql+asyncpg://...`.
2. Set real `GEMINI_API_KEY`, `SEARCH_API_KEY`, `SEARCH_ENGINE_ID`,
   `SECRET_KEY`.
3. Run `alembic upgrade head` (the Docker Compose backend command does this
   automatically on every start; for a non-Compose deployment run it once
   as a release step).
4. Start with a production ASGI server — `gunicorn` (already in
   `requirements.txt`) with `uvicorn.workers.UvicornWorker`, e.g.
   `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000`
   — rather than `uvicorn --reload`, which is dev-only.
5. Point the frontend's `NEXT_PUBLIC_API_URL` at the deployed backend URL.

See `docs/DEPLOYMENT_GUIDE.md` for the full walkthrough including Docker
Compose and manual deployment paths.

## 25. Complete Backend Summary

A strictly layered, fully async FastAPI backend whose central artifact is a
real LangGraph agent — not a simulated one — wired end-to-end from HTTP
request through tool execution to persisted, citation-validated claims. All
external I/O is mockable at a single seam per tool, all 36 tests run
offline and deterministically, and every failure mode in the project's
required failure-handling matrix has been exercised by an actual test
against actual (monkeypatched) failures.

## 26. What Was Used and Why

| Technology | Why |
|---|---|
| FastAPI + Uvicorn/Gunicorn | Async-native, `BackgroundTasks` for fire-and-continue agent execution, automatic OpenAPI schema. |
| Pydantic v2 (+ Pydantic Settings) | Validated env config at startup; validated request/response and tool I/O schemas everywhere. |
| SQLAlchemy 2.x (async) | ORM + async engine matching FastAPI's async model; `selectinload` for N+1-free citation queries. |
| PostgreSQL (+ SQLite for dev/test) | Relational schema with real FKs; SQLite/`aiosqlite` gives zero-config local dev and tests without changing any code. |
| Alembic | Versioned, reviewable schema migrations, kept in sync with the ORM models. |
| LangChain + LangGraph | LangGraph's `StateGraph` is the actual required agentic architecture; LangChain supplies the surrounding conventions. |
| Google Gemini (`google-generativeai`) | The project's sole required LLM provider, used for evidence extraction and final-answer synthesis. |
| httpx | Async HTTP client for both the Search API and page fetching, with per-call timeouts. |
| pytest + pytest-asyncio | Async-native test runner matching the fully-async application code. |
