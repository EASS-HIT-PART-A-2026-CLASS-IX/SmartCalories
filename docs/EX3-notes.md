# EX3 — SmartCalories submission notes (graders)

**Domain:** AI-powered calorie tracking & dieting agent
**Course:** EASS Semester B 2026, EX3
**Default API port:** `9000` (compose maps `9000:9000`; the demo script and runbook all use it)

> This file is the single source of truth for grading and is kept in sync with the code.
> Anything the product does *not* yet do is listed under **Known gaps** at the bottom rather
> than implied above — no claim here points at code that isn't in the repo.

## Repository layout
```
SmartCalories/
├── backend/                  # FastAPI + SQLModel + Alembic + smolagents agent (uv, Python 3.12)
├── frontend/                 # Vite + React 18 + Tailwind + shadcn + Firebase + TanStack Query (Node 22)
├── scripts/demo.sh           # graders' end-to-end walkthrough (no Firebase/Neon/paid key needed)
├── docs/                     # this file + runbooks
├── .claude/                  # phase plans, design docs, lessons (committed; partly aspirational)
└── README.md                 # quick start
```
The compose file lives at `backend/compose.yaml`.

## How to run

**Fastest path — the demo script (no Docker, no Firebase, no paid key):**
```bash
bash scripts/demo.sh
```
It auto-starts the backend on `:9000` against a throwaway SQLite DB in `ENVIRONMENT=dev`, seeds a
30-day dataset, and walks the REST surface (profile, diary, insights, water, TDEE, rate-limit
headers). Set `GEMINI_API_KEY` (or `GROQ_API_KEY`/`OPENROUTER_API_KEY`) first to also see a live
AI chat turn; without one the chat step is skipped with a clear note.

**Full stack via Docker (db + api + redis + web — fully local, no Neon/Redis Cloud needed):**
```bash
cd backend
cp .env.example .env             # AI keys optional; the DB + Redis run as local containers
docker compose up --build -d
docker compose ps                # db · api · redis · web · refresher
# open http://localhost:5173 → "Continue as guest" → type:  /log oatmeal 300
```

**Local dev without Docker:**
```bash
cd backend && uv sync
ENVIRONMENT=dev uv run uvicorn calorie_tracker.main:app --port 9000 --reload
# (SQLite tables auto-create on startup via init_db; Alembic is used for the Postgres path)
cd frontend && npm install && npm run dev      # http://localhost:5173
```

## Architecture (what actually runs)

```
React (Vite dev server)  ──HTTP + WebSocket──►  FastAPI  ──►  Postgres (compose-local / Neon in prod) / SQLite
  Firebase JS SDK                            │  ├─ Firebase Admin (verify ID token)
  TanStack Query                             │  ├─ smolagents ToolCallingAgent (LiteLLM)
  en + he (RTL)                              │  └─ rate-limit middleware ──► Redis
External: Gemini / Groq / OpenRouter / Ollama (LLM, with fallback) · Firebase Auth
```
Redis backs the rate-limit middleware (always-on) and the **rollup cache** written by the async
refresher (`scripts/refresh.py`). In the compose stack a dedicated **`refresher` worker** service
re-runs that script on an interval (`REFRESH_INTERVAL_SECONDS`, default hourly); the script itself
stays a one-shot process (idempotent, so looping is safe) and can also be driven by cron/launchd.

## Rubric mapping

| Rubric line | Where it lives | Status |
|---|---|---|
| **3+ cooperating services** | `backend/compose.yaml`: `api` (FastAPI :9000), `web` (React via Vite dev server :5173), `redis` (rate limiting). The three required cooperating services are **api + persistence (Neon/SQLite) + web**; the **LLM agent** (smolagents, embedded in api) is the 4th. | ✅ |
| **Persistence + migrations + seed (no `.db` artifacts)** | Neon Postgres in prod (`DATABASE_URL`), SQLite for dev/tests. Alembic in `backend/calorie_tracker/migrations/`. Seeding via `POST /auth/demo` (rich 30-day demo) and `POST /auth/playground` (per-user starter), both idempotent, in `services/demo_seed.py`. `.gitignore` excludes `*.db`, `data/`, `uploads/*`, `.env`. | ✅ |
| **4th microservice: LLM tool** | `calorie_tracker/ai/agent.py` — smolagents `ToolCallingAgent` driven through LiteLLM with a `_FallbackModel` chain (**Claude → Gemini → Groq → OpenRouter → Ollama**, each included only if its key is set; Anthropic/Claude is paid and tried first when configured) so a rate-limited/free provider falls through to the next. **12 diary/nutrition tools** in `ai/tools.py` (log/list/update/delete food, macros-today, remaining-budget, streak, add-water, get/set goals, TDEE, search-nutrition) + smolagents `WebSearchTool`. | ✅ |
| **Async refresh + Redis idempotency + `pytest.mark.anyio` test** | `calorie_tracker/scripts/refresh.py` — an async daily-rollup refresher with **bounded concurrency** (`asyncio.Semaphore`), **retries** (exponential backoff), and **Redis-backed idempotency** (each cached key paired with a sha256 digest; an unchanged rerun writes nothing). Run via `uv run python -m calorie_tracker.scripts.refresh`. Covered by `tests/test_refresh.py` (3 `pytest.mark.anyio` tests: write-then-idempotent, retry-on-transient-failure, bounded concurrency across users). Redis trace excerpt below. | ✅ |
| **Hashed credentials + JWT-protected routes + role checks** | **Firebase Auth** hashes passwords with Google's scrypt on Google's servers; ID tokens are RS256 JWTs verified by `firebase_admin.auth.verify_id_token` in `auth.py`. Every router except `/health` depends on `get_current_user`. Authorization gate enforced today: `require_not_anonymous` (guests get **403** on `/me/llm-key`). `require_role("admin")` factory exists in `deps.py` for admin-only routes. `tests/test_auth.py` + `tests/test_account.py`: **401** on missing/expired token, **403** for guests on a gated route, and per-user data isolation. | ⚠️ role gate is anon-vs-user, not admin (see Known gaps) |
| **Compose + Redis** | `backend/compose.yaml` (db · api · redis · web · refresher) — a single self-contained dev stack: local **Postgres** container, `backend/Dockerfile`-built api, Vite dev `web`, Redis (always on; no profile), and a **`refresher` worker** that loops `scripts/refresh.py` on a timer. `docker compose up` needs no external services. | ✅ |
| **Rate limit + `X-RateLimit-*` headers** | `calorie_tracker/rate_limit.py` Starlette middleware. Per-minute Redis counter; emits `X-RateLimit-Limit/Remaining/Reset` and `429` + `Retry-After`. **Falls open (no headers) when Redis is unreachable** — so headers appear in the compose stack, not in a bare `uvicorn` run. | ✅ |
| **Enhancement (rubric: "thoughtful")** | The **conversational AI agent that edits your diary by tool-calling**. Chat (`/chat/ws` WebSocket, plus REST `/chat/messages`) lets a user say "log two eggs and toast" or "how many calories do I have left?", and the agent calls the diary tools to actually mutate state and answer. Security-minded twist: users can **bring their own keys for any of the four chat providers** (Anthropic, Gemini, Groq, OpenRouter), stored Fernet-encrypted at rest (`services/secrets.py`, `/me/llm-key`) and tried first in fallback order. | ✅ |
| **Automated tests covering the enhancement** | `cd backend && uv run pytest` → **37 tests**: `test_chat_agent` (13, agent tools via a stubbed model), `test_account` (5, BYO-key + 403 gate), `test_auth` (9), `test_diary_insights` (7), `test_refresh` (3, async refresher via `pytest.mark.anyio`). The chat tests never call a real provider (see Lessons). | ✅ |
| **Demo script** | `scripts/demo.sh` — see "How to run". | ✅ |
| **CI** | `.github/workflows/ci.yml` runs `uv run pytest` on push/PR (in-memory SQLite + stubbed models, so no secrets needed). Schemathesis is documented as a manual run in `docs/runbooks/compose.md` (every route needs an auth token, so it isn't in required CI). | ✅ pytest in CI / ⚠️ Schemathesis manual |

## Async refresher — Redis trace excerpt

Seeding the demo user (30 days of diary) and running the refresher twice against a real local
Redis. The second run shows idempotency: the 7 day-rollup keys are unchanged so they're skipped,
and only the `:summary` key (which carries a fresh `generated_at` timestamp) is rewritten.

```text
$ uv run python -m calorie_tracker.scripts.refresh        # run 1 (cold cache)
INFO __main__: refresh complete: users=1 written=8 skipped(idempotent)=0 retries=0 errors=0

$ uv run python -m calorie_tracker.scripts.refresh        # run 2 (unchanged data)
INFO __main__: refresh complete: users=1 written=1 skipped(idempotent)=7 retries=0 errors=0

$ redis-cli --raw get rollup:demo-uid:summary
{"days_cached": ["2026-06-19", ... "2026-06-25"], "generated_at": "2026-06-25T10:15:33+00:00",
 "streak": 7, "uid": "demo-uid"}
```

## Endpoint surface (real)
- `GET /health`, `GET /health/ready`
- `GET/PATCH /users/me`, `GET/PUT /users/me/goals`, `GET/PUT /users/me/preferences`
- `GET/PUT/DELETE /me/llm-key` (non-anonymous only)
- `GET/POST /diary`, `GET /diary/today`, `PATCH/DELETE /diary/{id}`
- `GET /insights/macros/today`, `GET /insights/macros/range?days=`, `GET /insights/streak`, `POST /insights/tdee`
- `POST /logs/water`, `GET /logs/range`
- `POST /chat/messages` (create-or-append), `POST /chat/sessions/{id}/messages`, session CRUD + search, `WS /chat/ws` (live tool + token events)
- `POST /auth/demo`, `POST /auth/playground` (dev/seed helpers)

## Beyond-rubric extras
- **Multi-provider LLM resilience** — automatic fallback across Gemini, Groq, OpenRouter, and a local Ollama backstop, so the free tier degrades gracefully instead of erroring.
- **Bring-your-own API keys** — signed-in users store personal keys for any of the four chat providers (Anthropic, Gemini, Groq, OpenRouter), encrypted at rest with Fernet (AES-128-CBC + HMAC); the agent uses them first in fallback order, and only a masked last-4 hint is ever read back. The Settings modal explains the fallback strategy and recommends adding keys in that order.
- **Bilingual UI** — English + Hebrew with full RTL.
- **ChatGPT-style streaming** — the chat WebSocket emits typed events (`session`/`tool`/`message`/`title`/`done`/`error`); the client renders a thinking pill, animated tool-call chips, paced token output, and a Stop button.
- **Friendly provider-error mapping** — raw rate-limit/auth/overload exceptions become clear, actionable user messages (`routers/chat.py`).

## Security: credential & key rotation
- **Firebase service-account JSON**: rotate via Google Cloud Console → IAM → service account → new key, then update `FIREBASE_CREDENTIALS_PATH`/`FIREBASE_CREDENTIALS_JSON`. ID tokens already issued stay valid until natural expiry (~1h).
- **`SECRET_KEY`** (derives the Fernet key for stored user API keys): rotating it invalidates stored keys by design — users simply re-enter their key in Settings. Must be set in prod (dev uses an insecure fallback with a logged warning).

## Known gaps (honest accounting)
These are acknowledged, not hidden:
- **The worker loops the refresher, not a queue.** `scripts/refresh.py` is the async refresher (bounded concurrency + retries + Redis idempotency + `pytest.mark.anyio` tests). The compose `refresher` service runs it on a timer (`REFRESH_INTERVAL_SECONDS`, default hourly), satisfying the spec's `docker compose up … worker` line. It is **not** a message-queue consumer: there's no real event the app enqueues, so an `arq`-style queue would be empty scaffolding. Nothing in the request path depends on the cache (the insights routes still compute live), so a missed tick only means a slightly cold cache — the rollup cache currently has no reader yet, so the worker is warm async infrastructure rather than a load-bearing one.
- **Redis is used by two things** — the rate-limit middleware (always-on) and the refresher's rollup cache. Still no queue.
- **Role check** enforced on a live route today is anonymous-vs-user (`require_not_anonymous`); the `require_role("admin")` factory is implemented and tested at the unit level but not yet mounted on an admin-only route.
- **CI runs `pytest`; Schemathesis is manual.** `.github/workflows/ci.yml` runs the suite on push/PR. Schemathesis isn't in required CI (every route needs an auth token) but the command is documented in `docs/runbooks/compose.md`.
- The `.claude/` master plan describes features that were intentionally **descoped** (MCP server, weekly-report worker, barcode/OpenFoodFacts, recipes/planner/shopping, a dedicated insights/history/profile tab set). They are not in the codebase; treat the plan as historical intent, this file as ground truth.

## AI Assistance section
Built with assistance from Claude Code. Notable points and verifications:
- Architecture was planned in plan mode (`.claude/plans/ex3-master-plan.md`); decision points (Firebase vs bcrypt, Gemini vs others, Neon vs SQLite, Pydantic AI vs smolagents) were chosen interactively. The chat agent was later migrated from Pydantic AI to smolagents/LiteLLM for multi-provider fallback.
- Every phase has a verification step — `uv run pytest` green (37 tests), `npm run build` green, and the manual smoke test in `scripts/demo.sh`.
- All changes are in the commit history; nothing was auto-merged.

## Lessons learned
- **Free-tier LLMs need fallback.** A single provider rate-limits constantly, so the agent chains Gemini → Groq → OpenRouter → Ollama and advances on any error.
- **smolagents agents are sync generators.** Streaming over WebSocket runs `agent.run(task, stream=True)` in a thread and forwards tool events through an asyncio queue, keeping all DB-session access on one thread.
- **Tests must not hit a real model.** Chat tests stub the model so the suite is deterministic and burns no quota (see `.claude/lessons/`).
- **Keep the dependency surface honest.** Periodic cleanup removed an unused worker, cache, refresh script, and ~8 orphaned deps (pandas, reportlab, fastmcp, logfire, …) left over from descoped features.
