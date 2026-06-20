# EX3 — SmartCalories submission notes (graders)

**Domain:** AI-powered calorie tracking & dieting agent  
**Built:** 2026-04-06 → 2026-05-05  
**Course:** EASS Semester B 2026, EX3

## Repository layout
```
SmartCalories/
├── backend/                  # FastAPI + SQLModel + Pydantic AI + arq + FastMCP (uv project, Python 3.12)
├── frontend/                 # Vite + React 18 + Tailwind + shadcn + Firebase + TanStack Query (Node 22)
├── docs/                     # this file + runbooks
├── .claude/                  # phase plans, design docs, skills, lessons (committed)
├── compose.yaml              # under backend/, see below
└── README.md                 # quick start
```

## How to run (graders' shortcut)
```bash
cd backend
cp .env.example .env             # set DATABASE_URL (Neon Postgres), GEMINI_API_KEY (optional)
docker compose up --build -d
docker compose ps                # api · worker · redis · web (· mcp once enabled)

# Open http://localhost:5173 → continue as guest → /log oatmeal 300 → see the streaming agent reply
```
Local dev without Docker: `cd backend && uv sync && uv run alembic upgrade head && uv run python -m calorie_tracker.scripts.seed && uv run uvicorn calorie_tracker.main:app --reload`. Frontend: `cd frontend && npm install && npm run dev`.

## Rubric mapping

| Rubric line | Where it lives |
|---|---|
| **3+ cooperating services** | `compose.yaml` runs `api`, `worker`, `redis`, `web`. **5th** MCP server (`calorie_tracker/mcp/server.py`) reuses the same image; commented in compose, runnable standalone over stdio. |
| **Persistence + migrations + seed (no `.db` artifacts)** | Neon cloud Postgres in prod (`DATABASE_URL`), in-memory SQLite in tests. `backend/alembic.ini` + `backend/calorie_tracker/migrations/`. `seed.py` writes via SQLModel; idempotent. `.gitignore` excludes `*.db`, `data/`, `uploads/*`. |
| **LLM microservice via Pydantic AI** | `calorie_tracker/ai/agent.py` (Gemini 2.5 Flash via `pydantic-ai-slim[google]`); 12 tools in `ai/tools.py`. Vision agent in `ai/vision.py`. |
| **Async refresh script + Redis idempotency + `pytest.mark.anyio` test** | `calorie_tracker/scripts/refresh.py` (anyio `Semaphore(8)` + tenacity retries + Redis `SET NX EX`). `tests/test_refresh.py` (3 anyio tests: idempotency, retry, permanent failure). |
| **Hashed credentials + JWT-protected routes + role checks** | **Firebase Auth** stores password hashes via Google's modified scrypt on Google's servers. ID tokens are RS256 JWTs verified by `firebase_admin.auth.verify_id_token` in `auth.py`. Role custom claims mirror onto `User.role`; `require_role("admin")` factory enforces. `tests/test_auth.py`: 401 on missing/expired, 403 on wrong scope, per-user data isolation. Rotation procedure: rotate the Firebase service-account JSON via Google Cloud Console → upload new path to `FIREBASE_CREDENTIALS_PATH`; tokens already in flight stay valid until natural expiry (~1h). |
| **Compose + Redis + worker** | `backend/compose.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`. arq worker in `calorie_tracker/workers/worker.py`. |
| **Rate limit + `X-RateLimit-*` headers** | `calorie_tracker/rate_limit.py` Starlette middleware. Per-minute Redis counter; emits `Limit/Remaining/Reset` and 429 with `Retry-After`. |
| **Enhancement (rubric: "thoughtful")** | **AI weekly summary report**: pandas aggregates → small Pydantic AI narrative agent → markdown + CSV + PDF (reportlab) under `uploads/{uid}/reports/`. `routers/reports.py` + `services/reports.py` + `tests/test_reports.py`. |
| **Automated tests** | `cd backend && uv run pytest` — **59 tests**: `test_entries`, `test_auth`, `test_diary_insights`, `test_recipes_planner_shopping`, `test_barcode`, `test_chat_agent`, `test_photo`, `test_migrations_and_seed`, `test_refresh`, `test_reports`, `test_mcp`, `test_api_keys`. |
| **Demo script** | `.claude/skills/run-stack.md` is the runbook; per-phase plans in `.claude/plans/phase-NN-*.md` document each milestone. |

## Beyond-rubric extras
- **MCP server** (5th microservice) — Claude Desktop / Cursor / Zed integration. Profile → Developer card mints **personal API keys** (`sck_…`, sha256-hashed at rest, revocable). MCP server accepts an API key OR a Firebase ID token; tools execute under the key's owning user. See `.claude/plans/phase-15-api-keys.md`.
- **Image → nutrition** via Gemini 2.5 Flash multimodal. `POST /photo/scan` ingests a meal photo and (optionally) auto-creates a diary entry.
- **OpenFoodFacts barcode lookup** with Redis-backed caching.
- **Bilingual UI** — English + Hebrew with full RTL support.
- **Slash commands** in chat (`/log`, `/macros`, `/recipes`, `/water`, etc.) routed through the agent so they get the LLM's natural-language acknowledgement.
- **ChatGPT-style streaming** — the chat composer renders typed SSE events: thinking pill, animated tool-call chips ("Logging your meal…", "Looking up the barcode…"), token-by-token text with a blinking caret, and a Stop button wired to `AbortController`.

## AI Assistance section
This project was built with assistance from Claude Code (Opus 4.7). Notable prompts and verifications:
- Architecture planning happened in plan mode (see `.claude/plans/ex3-master-plan.md`); the model proposed several decision points and we picked tradeoffs together (Firebase vs bcrypt, Gemini vs Gemma, Neon vs SQLite).
- Each phase has a verification step — pytest suite green, Vite build green, manual smoke-test commands documented in `.claude/skills/run-stack.md`.
- Every code change was reviewed in this commit history; nothing was auto-merged.

## Lessons learned
- **Pydantic AI 1.x's** Google provider validates the API key at `Agent(...)` construction. We fall back to `TestModel` in dev/CI and override the model per test (see `.claude/lessons/2026-05-04-pydantic-ai-1x-gotchas.md`).
- Mixing async FastAPI handlers with sync SQLModel sessions and `agent.run_sync` requires `fastapi.concurrency.run_in_threadpool` to keep all session ops on one thread.
- Python 3.13.0a3 (preinstalled on macOS) breaks `anyio` because of incomplete PEP 696 support. Pin to Python 3.12 via `.python-version`.
