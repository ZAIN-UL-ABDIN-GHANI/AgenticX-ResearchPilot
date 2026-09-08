# ResearchPilot AI — Deployment Guide

This covers taking the project from local development to a running
production-style deployment. Two paths are documented: Docker Compose on a
single host, and a manual/managed-services deployment. Both assume you have
real `GEMINI_API_KEY`, `SEARCH_API_KEY`, and `SEARCH_ENGINE_ID` values.

---

## 1. Production checklist

- [ ] Real Gemini + Google Custom Search credentials set (not the
      placeholder defaults in `.env.example`).
- [ ] `SECRET_KEY` set to a long, random, unique value — never the example
      placeholder.
- [ ] `DEBUG=false`.
- [ ] `DATABASE_URL` points at a real, backed-up PostgreSQL instance using
      the `postgresql+asyncpg://` scheme (the async driver — see
      `docs/BACKEND_DOCUMENTATION.md` §19 for why the scheme matters).
- [ ] `ALLOWED_ORIGINS` restricted to your actual frontend origin(s), not
      left as `*`/localhost defaults.
- [ ] `NEXT_PUBLIC_API_URL` (frontend) points at the deployed backend's
      public URL.
- [ ] Migrations applied (`alembic upgrade head`) before traffic is routed
      to a new backend version.
- [ ] Backend served by a production ASGI server (`gunicorn` +
      `uvicorn.workers.UvicornWorker`), not `uvicorn --reload`.

---

## 2. Docker Compose on a single host

This is the fastest path to a working production-like deployment and is
appropriate for a small-to-medium deployment on one VM.

```bash
git clone <your-repo-url> researchpilot-ai
cd researchpilot-ai
cp .env.example .env
# edit .env with real production values (see checklist above)

docker compose up -d --build
```

For a real deployment, additionally:

- Put a reverse proxy (Caddy/nginx/Traefik) in front of the `frontend` (port
  3000) and `backend` (port 8000) containers to terminate TLS and serve both
  under one domain (e.g. `/api/*` → backend, everything else → frontend).
- Set `restart: unless-stopped` on all three services in
  `docker-compose.yml` (or use `docker compose up -d --build` with a process
  supervisor / systemd unit wrapping the compose command) so the stack
  survives a host reboot.
- Mount `postgres_data` on durable storage and set up regular
  `pg_dump` backups — the compose file's named volume is durable across
  container recreation but not a substitute for off-host backups.
- Remove the backend's dev bind-mount (`./backend:/app`) and `--reload` flag
  for production — rebuild the image on every deploy instead of relying on
  a live-reloading mount.

---

## 3. Manual / managed-services deployment

Appropriate if you want the backend and frontend on different platforms
(e.g. a managed Postgres, a container platform for the backend, and a
static/edge host for the frontend).

### Database
Provision a managed PostgreSQL 16 instance (RDS, Cloud SQL, etc.). Note the
connection string and convert it to the async scheme:
`postgresql+asyncpg://user:pass@host:5432/dbname`.

### Backend
```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000
```
Set all required environment variables (see `.env.example`) in your
platform's secret/config management rather than a committed `.env` file.
Point your platform's health check at `GET /health`.

### Frontend
```bash
cd frontend
npm ci
NEXT_PUBLIC_API_URL=https://api.yourdomain.com npm run build
npm start   # or deploy the .next output to your Node-capable host
```
If deploying to a platform that builds from source (rather than running
`npm start` yourself), set `NEXT_PUBLIC_API_URL` as a build-time environment
variable — it's baked into the client bundle at build time, not read at
request time.

---

## 4. Migrations in production

Always run `alembic upgrade head` as an explicit release step (or, if using
Docker Compose as-is, it runs automatically on backend container start via
the `command:` override) **before** traffic reaches a version of the backend
that expects the new schema. Never rely on `Base.metadata.create_all` in
production — that path exists only so local dev/tests work with zero setup;
`main.py`'s startup hook (`create_all`) is a convenience for SQLite dev, and
is a no-op against tables that already exist (via Alembic) in a real
Postgres deployment.

To roll back a bad migration: `alembic downgrade -1` (one step) or
`alembic downgrade <revision>`. Verified in this project: a full
`upgrade head` → `downgrade base` cycle cleanly creates and drops all five
tables with no orphaned objects.

---

## 5. Scaling notes

- The backend is stateless per-request except for the in-process
  `BackgroundTasks` executing an agent run — if you run multiple backend
  replicas behind a load balancer, a research run's background execution
  stays on whichever instance received the `POST`, which is fine (the
  frontend polls by `research_id` against the shared database, not against
  a specific instance), but a rolling deploy that kills that instance mid-run
  will orphan that run in `status: "running"` forever. For a
  multi-replica production deployment, replace `BackgroundTasks` with a real
  task queue (Celery/RQ/Cloud Tasks) so an in-flight run survives an
  instance recycling — noted as a future-scalability item in
  `docs/SYSTEM_DESIGN.md` §18.
- The frontend is fully stateless and horizontally scalable as-is.
- PostgreSQL connection pool sizing (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` in
  `.env.example`) should be tuned relative to `(backend replica count) ×
  (pool size + max overflow) < your Postgres max_connections`.
