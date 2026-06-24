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
docker compose ps                # db · api · redis · web
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
Redis is used **only** by the rate-limit middleware. There is no background worker or cache layer.

## Rubric mapping

| Rubric line | Where it lives | Status |
|---|---|---|
| **3+ cooperating services** | `backend/compose.yaml`: `api` (FastAPI :9000), `web` (React via Vite dev server :5173), `redis` (rate limiting). The three required cooperating services are **api + persistence (Neon/SQLite) + web**; the **LLM agent** (smolagents, embedded in api) is the 4th. | ✅ |
| **Persistence + migrations + seed (no `.db` artifacts)** | Neon Postgres in prod (`DATABASE_URL`), SQLite for dev/tests. Alembic in `backend/calorie_tracker/migrations/`. Seeding via `POST /auth/demo` (rich 30-day demo) and `POST /auth/playground` (per-user starter), both idempotent, in `services/demo_seed.py`. `.gitignore` excludes `*.db`, `data/`, `uploads/*`, `.env`. | ✅ |
| **4th microservice: LLM tool** | `calorie_tracker/ai/agent.py` — smolagents `ToolCallingAgent` driven through LiteLLM with a `_FallbackModel` chain (**Claude → Gemini → Groq → OpenRouter → Ollama**, each included only if its key is set; Anthropic/Claude is paid and tried first when configured) so a rate-limited/free provider falls through to the next. **13 diary/nutrition tools** in `ai/tools.py` (log/list/update/delete food, macros-today, remaining-budget, streak, add-water, get/set goals, TDEE, analyze-image, search-nutrition) + smolagents `WebSearchTool`. | ✅ |
| **Async refresh + Redis idempotency + `pytest.mark.anyio` test** | Intentionally **removed** during cleanup — it was product-unused scaffolding and its Redis use conflicted with the "Redis = rate limiting only" decision. | ❌ removed (see Known gaps) |
| **Hashed credentials + JWT-protected routes + role checks** | **Firebase Auth** hashes passwords with Google's scrypt on Google's servers; ID tokens are RS256 JWTs verified by `firebase_admin.auth.verify_id_token` in `auth.py`. Every router except `/health` depends on `get_current_user`. Authorization gate enforced today: `require_not_anonymous` (guests get **403** on `/me/llm-key`). `require_role("admin")` factory exists in `deps.py` for admin-only routes. `tests/test_auth.py` + `tests/test_account.py`: **401** on missing/expired token, **403** for guests on a gated route, and per-user data isolation. | ⚠️ role gate is anon-vs-user, not admin (see Known gaps) |
| **Compose + Redis** | `backend/compose.yaml` (db · api · redis · web) — a single self-contained dev stack: local **Postgres** container, `backend/Dockerfile`-built api, Vite dev `web`, and Redis (always on; no profile). `docker compose up` needs no external services. No background worker (removed). | ✅ / ⚠️ no worker |
| **Rate limit + `X-RateLimit-*` headers** | `calorie_tracker/rate_limit.py` Starlette middleware. Per-minute Redis counter; emits `X-RateLimit-Limit/Remaining/Reset` and `429` + `Retry-After`. **Falls open (no headers) when Redis is unreachable** — so headers appear in the compose stack, not in a bare `uvicorn` run. | ✅ |
| **Enhancement (rubric: "thoughtful")** | The **conversational AI agent that edits your diary by tool-calling** + **image → nutrition** photo scan. Chat (`/chat/ws` WebSocket, plus REST `/chat/messages`) lets a user say "log two eggs and toast" or `/budget`, and the agent calls the diary tools to actually mutate state and answer. `POST /photo/scan` runs a Gemini-vision structured-output agent (`ai/vision.py`, pydantic-ai) to turn a meal photo into a `FoodEntry`. Security-minded twist: users can **bring their own Gemini key**, stored Fernet-encrypted at rest (`services/secrets.py`, `/me/llm-key`). | ✅ |
| **Automated tests covering the enhancement** | `cd backend && uv run pytest` → **38 tests**: `test_chat_agent` (14, agent tools via a stubbed model), `test_photo` (3, vision stubbed), `test_account` (5, BYO-key + 403 gate), `test_auth` (9), `test_diary_insights` (7). The chat/vision tests never call a real provider (see Lessons). | ✅ |
| **Demo script** | `scripts/demo.sh` — see "How to run". | ✅ |

## Endpoint surface (real)
- `GET /health`, `GET /health/ready`
- `GET/PATCH /users/me`, `GET/PUT /users/me/goals`, `GET/PUT /users/me/preferences`
- `GET/PUT/DELETE /me/llm-key` (non-anonymous only)
- `GET/POST /diary`, `GET /diary/today`, `PATCH/DELETE /diary/{id}`
- `GET /insights/macros/today`, `GET /insights/macros/range?days=`, `GET /insights/streak`, `POST /insights/tdee`
- `POST /logs/water`, `GET /logs/range`
- `POST /chat/messages` (create-or-append), `POST /chat/sessions/{id}/messages`, `POST /chat/commands`, session CRUD + search, `WS /chat/ws` (live tool + token events)
- `POST /photo/scan` (multipart → vision)
- `POST /auth/demo`, `POST /auth/playground` (dev/seed helpers)

## Beyond-rubric extras
- **Multi-provider LLM resilience** — automatic fallback across Gemini, Groq, OpenRouter, and a local Ollama backstop, so the free tier degrades gracefully instead of erroring.
- **Bring-your-own API key** — signed-in users store a personal Gemini key, encrypted at rest with Fernet (AES-128-CBC + HMAC); only a masked last-4 hint is ever read back.
- **Image → nutrition** via Gemini multimodal — `POST /photo/scan` ingests a meal photo and can auto-create a diary entry.
- **Bilingual UI** — English + Hebrew with full RTL.
- **ChatGPT-style streaming** — the chat WebSocket emits typed events (`session`/`tool`/`message`/`title`/`done`/`error`); the client renders a thinking pill, animated tool-call chips, paced token output, and a Stop button.
- **Friendly provider-error mapping** — raw rate-limit/auth/overload exceptions become clear, actionable user messages (`routers/chat.py`).

## Security: credential & key rotation
- **Firebase service-account JSON**: rotate via Google Cloud Console → IAM → service account → new key, then update `FIREBASE_CREDENTIALS_PATH`/`FIREBASE_CREDENTIALS_JSON`. ID tokens already issued stay valid until natural expiry (~1h).
- **`SECRET_KEY`** (derives the Fernet key for stored user API keys): rotating it invalidates stored keys by design — users simply re-enter their key in Settings. Must be set in prod (dev uses an insecure fallback with a logged warning).

## Known gaps (honest accounting)
These are acknowledged, not hidden:
- **Async worker + async refresher (Session 09) were intentionally removed.** The arq worker had no real job and nothing enqueued it, and `scripts/refresh.py` was product-unused scaffolding whose Redis idempotency conflicted with the decision that **Redis backs only the rate limiter**. We chose a clean codebase over those two rubric checkboxes. Reinstating them later means adding a worker job the app actually enqueues + a refresher with its own backing store.
- **Redis is now used by exactly one thing** — the rate-limit middleware. No cache, no queue.
- **Role check** enforced on a live route today is anonymous-vs-user (`require_not_anonymous`); the `require_role("admin")` factory is implemented and tested at the unit level but not yet mounted on an admin-only route.
- **No CI workflow / Schemathesis** yet (`uv run pytest` is run locally).
- The `.claude/` master plan describes features that were intentionally **descoped** (MCP server, weekly-report worker, barcode/OpenFoodFacts, recipes/planner/shopping, a dedicated insights/history/profile tab set). They are not in the codebase; treat the plan as historical intent, this file as ground truth.

## AI Assistance section
Built with assistance from Claude Code. Notable points and verifications:
- Architecture was planned in plan mode (`.claude/plans/ex3-master-plan.md`); decision points (Firebase vs bcrypt, Gemini vs others, Neon vs SQLite, Pydantic AI vs smolagents) were chosen interactively. The chat agent was later migrated from Pydantic AI to smolagents/LiteLLM for multi-provider fallback; vision stayed on pydantic-ai.
- Every phase has a verification step — `uv run pytest` green (38 tests), `npm run build` green, and the manual smoke test in `scripts/demo.sh`.
- All changes are in the commit history; nothing was auto-merged.

## Lessons learned
- **Free-tier LLMs need fallback.** A single provider rate-limits constantly, so the agent chains Gemini → Groq → OpenRouter → Ollama and advances on any error.
- **smolagents agents are sync generators.** Streaming over WebSocket runs `agent.run(task, stream=True)` in a thread and forwards tool events through an asyncio queue, keeping all DB-session access on one thread.
- **Tests must not hit a real model.** Chat/vision tests stub the model so the suite is deterministic and burns no quota (see `.claude/lessons/`).
- **Keep the dependency surface honest.** Periodic cleanup removed an unused worker, cache, refresh script, and ~8 orphaned deps (pandas, reportlab, fastmcp, logfire, …) left over from descoped features.
