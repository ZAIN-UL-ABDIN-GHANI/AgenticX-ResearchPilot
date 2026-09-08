# ResearchPilot AI — Setup Guide

Two paths: **Docker Compose** (recommended, one command) or **manual local
development** (useful for iterating on the backend/frontend directly).

---

## Prerequisites

| Tool | Version | Needed for |
|---|---|---|
| Docker + Docker Compose | recent | Docker path |
| Python | 3.11+ | Manual backend |
| Node.js | 18+ | Manual frontend |
| PostgreSQL | 16 (or use Docker for just this) | Manual backend, production |
| Google Gemini API key | — | Real (non-mocked) agent runs |
| Google Custom Search API key + Search Engine ID | — | Real (non-mocked) agent runs |

Get a Gemini key at https://ai.google.dev/. Get a Custom Search API key and
Search Engine ID at https://programmablesearchengine.google.com/. The app
runs perfectly well without either for local development and the full test
suite (which mocks every external call) — you only need real keys to see
the agent actually search/fetch/summarize live content.

---

## Path A — Docker Compose (recommended)

```bash
# 1. Clone/unzip the project, then from the project root:
cp .env.example .env

# 2. Edit .env and set at minimum:
#    GEMINI_API_KEY=...
#    SEARCH_API_KEY=...
#    SEARCH_ENGINE_ID=...
#    SECRET_KEY=<any long random string>

# 3. Start everything
docker compose up --build
```

This starts three containers: `postgres` (with a healthcheck gating the
backend), `backend` (runs `alembic upgrade head` then serves on `:8000`),
and `frontend` (serves on `:3000`). Once `backend` reports healthy:

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs
- Backend health: http://localhost:8000/health

Stop with `docker compose down`; add `-v` to also drop the Postgres volume.

---

## Path B — Manual local development

### 1. Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp ../.env.example .env
# Edit .env: for local dev without Postgres running, you can simply use:
#   DATABASE_URL=sqlite+aiosqlite:///./dev.db
# or point at a local Postgres instance with the postgresql+asyncpg:// scheme.

# If using Postgres, apply migrations:
alembic upgrade head

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/health` → `{"status":"healthy",...}`.

Run the backend tests (fully offline, no keys needed):
```bash
pytest tests/ -v
```

### 2. Frontend

```bash
cd frontend
npm install

cp ../.env.example .env.local   # or just set NEXT_PUBLIC_API_URL
# Ensure:
#   NEXT_PUBLIC_API_URL=http://localhost:8000

npm run dev
```

Open http://localhost:3000. Run the frontend tests:
```bash
npm test
```

### 3. Database (manual Postgres, if not using SQLite for dev)

```bash
docker run -d --name researchpilot-postgres \
  -e POSTGRES_USER=researcher \
  -e POSTGRES_PASSWORD=researcher_password \
  -e POSTGRES_DB=researchpilot_db \
  -p 5432:5432 postgres:16-alpine

# then in backend/.env:
# DATABASE_URL=postgresql+asyncpg://researcher:researcher_password@localhost:5432/researchpilot_db
cd backend && alembic upgrade head
```

---

## Verifying the full stack works

1. Open http://localhost:3000, submit a question (e.g. *"What are current
   techniques for reducing LLM hallucinations?"*).
2. You should land on `/research/{id}` and see the live workspace: status,
   step counter, and a tool-call timeline filling in as the agent runs.
3. Once it finishes, the view swaps to the results screen: final answer
   with `[1][2]...` citation markers, a citations section, and the full
   source list.
4. Cross-check via the API directly: `curl http://localhost:8000/api/v1/research/{id}/claims`
   should show the same claims/citations rendered in the UI.

If you don't have real Gemini/Search API keys configured, step 2–3 will
still run correctly, but the search tool will fail (no network access to
Google's API) and the run will correctly complete as `status: "failed"`
with an honest "insufficient evidence" message — see
`docs/TROUBLESHOOTING.md` if you expected a real answer and got this.
