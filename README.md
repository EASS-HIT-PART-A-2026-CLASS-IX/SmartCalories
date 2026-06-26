# SmartCalories

AI-powered calorie tracking & dieting agent. You chat with an assistant that logs your meals
and answers questions about your macros — backed by a FastAPI service, a SQL persistence layer,
Redis (rate limiting), and a React frontend.

EASS Semester B 2026 — EX3 final project. Grader notes: **[`docs/EX3-notes.md`](docs/EX3-notes.md)**.

## What's in here
```
backend/     FastAPI + SQLModel + Alembic + smolagents agent (LiteLLM)   (uv, Python 3.12)
frontend/    Vite + React 18 + Tailwind + shadcn + Firebase + TanStack Query           (Node 22)
scripts/     demo.sh — one-command end-to-end walkthrough
docs/        EX3 notes + compose runbook
```

## Quick start — the demo script
The fastest way to see it work. No Firebase, no Neon, no paid API key required:
```bash
bash scripts/demo.sh
```
It auto-starts the backend on `:9000` (throwaway SQLite, `ENVIRONMENT=dev`), seeds a 30-day
dataset, and walks the REST surface (profile, diary, insights, water, TDEE, rate-limit headers).
Set `GEMINI_API_KEY` (or `GROQ_API_KEY` / `OPENROUTER_API_KEY`) beforehand to also see a live AI
chat turn.

## Run the backend
Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
```bash
cd backend
uv sync
cp .env.example .env                 # optional: set DATABASE_URL (Neon) + AI keys; SQLite is the default
ENVIRONMENT=dev uv run uvicorn calorie_tracker.main:app --port 9000 --reload
```
Base URL: `http://127.0.0.1:9000`. Tables auto-create on startup (SQLite path); for Postgres run
`uv run alembic upgrade head`.

### Interactive docs
Open **http://127.0.0.1:9000/docs** (Swagger UI) — "Try it out" on any route. ReDoc at `/redoc`.

### Auth in one line (dev)
Every route except `/health` requires `Authorization: Bearer <Firebase ID token>`. In
`ENVIRONMENT=dev` the literal token `demo-token` is accepted as a stand-in demo user, so you can
explore without Firebase:
```bash
# seed the demo user's data (dev only) and grab the token
curl -s -X POST http://127.0.0.1:9000/auth/demo | python3 -m json.tool

# then call any route as that user
curl -s http://127.0.0.1:9000/diary/today        -H 'Authorization: Bearer demo-token' | python3 -m json.tool
curl -s http://127.0.0.1:9000/insights/macros/today -H 'Authorization: Bearer demo-token' | python3 -m json.tool
curl -s -X POST http://127.0.0.1:9000/diary \
  -H 'Authorization: Bearer demo-token' -H 'Content-Type: application/json' \
  -d '{"name":"Oatmeal","calories":300,"meal":"breakfast"}' | python3 -m json.tool
```
Key route groups: `/users/me`, `/me/llm-key`, `/diary`, `/insights`, `/logs`, `/chat`
(REST + `WS /chat/ws`). Full list in `docs/EX3-notes.md` or `/docs`.

## Run the frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — click "Continue as guest", then type:  /log oatmeal 300
```

## Full stack with Docker
```bash
cd backend
docker compose up --build      # db (Postgres) · api :9000 · web :5173 · redis · refresher — all local
```
See **[`docs/runbooks/compose.md`](docs/runbooks/compose.md)** for verification commands.

## Tests
```bash
cd backend && uv run pytest          # 37 tests; chat tests use a stub model (no quota used)
```
CI runs the same suite on every push/PR (`.github/workflows/ci.yml`).

## Async rollup refresher
An async job recomputes each user's daily macro rollups + streak and caches them in Redis
(bounded concurrency, retries, idempotent writes). In the compose stack the `refresher` worker
loops it on a timer (`REFRESH_INTERVAL_SECONDS`, default hourly); you can also run it by hand or
on a cron/launchd timer:
```bash
cd backend && uv run python -m calorie_tracker.scripts.refresh
```
Details + a Redis trace are in [`docs/EX3-notes.md`](docs/EX3-notes.md); compose usage in
[`docs/runbooks/compose.md`](docs/runbooks/compose.md).

## AI Assistance
This project was built with Claude Code (Anthropic). Planning was done in plan mode
(`.claude/plans/`), with architecture decisions chosen interactively (Firebase vs bcrypt, the
Gemini→Groq→OpenRouter→Ollama fallback, Neon vs SQLite, and migrating the chat agent from
Pydantic AI to smolagents/LiteLLM). Every change was verified locally — `uv run pytest` green,
`npm run build` green, and the `scripts/demo.sh` smoke test — and reviewed in the commit history;
nothing was auto-merged. See `docs/EX3-notes.md` for the full rubric mapping and a candid
**Known gaps** section.
