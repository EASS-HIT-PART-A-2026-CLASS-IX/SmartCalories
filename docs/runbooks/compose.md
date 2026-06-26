# Compose runbook

The compose file is at `backend/compose.yaml` — a single self-contained dev stack. It brings up
five services: `db` (local **Postgres**), `api` (FastAPI + uvicorn `--reload` on :9000), `web`
(Vite dev server with HMR on :5173, reads `frontend/.env` live), `redis` (rate-limit middleware +
rollup cache), and `refresher` (the async worker that re-runs `scripts/refresh.py` on a timer).
Everything runs locally — **no external Neon or Redis Cloud needed**; the api points at the
in-compose Postgres + Redis containers regardless of the `DATABASE_URL`/`REDIS_URL` in `.env`
(those are only for non-Docker runs and for prod via `render.yaml`).

## Bring up the stack
```bash
cd backend
cp .env.example .env             # AI keys (ANTHROPIC/GEMINI/…) optional; DB + Redis come from compose
docker compose up --build -d
docker compose ps                # db · api · web · redis · refresher
docker compose logs -f api
```

## Verify the stack
```bash
curl -s localhost:9000/health                                        # {"status":"ok","app":"SmartCalories"}
curl -s localhost:9000/health/ready                                  # {"status":"ready"}
curl -s -D - -o /dev/null localhost:9000/health | grep -i ratelimit  # X-RateLimit-* headers (Redis is up)
docker compose exec redis redis-cli ping                             # PONG
docker compose exec db pg_isready -U smartcalories                   # accepting connections
```

## Database & seed
`db` is a local Postgres container; data persists in the `sc_pgdata` volume. On boot the api runs
`alembic upgrade head` automatically, creating the schema on first start. Seed demo data via the
dev-only endpoint:
```bash
curl -s -X POST localhost:9000/auth/demo | python3 -m json.tool       # returns the dev `demo-token`
curl -s localhost:9000/diary/today -H 'Authorization: Bearer demo-token' | python3 -m json.tool
```

## Async rollup refresher (Session 09)
Recompute + cache each user's daily macro rollups in Redis (bounded concurrency, retries,
idempotent writes). The `refresher` compose service runs it on a loop (default every 3600s; set
`REFRESH_INTERVAL_SECONDS` to change it) — watch it tick, or trigger a run by hand:
```bash
docker compose logs -f refresher                                    # "refresh complete: users=… written=… skipped(idempotent)=…"
docker compose exec api python -m calorie_tracker.scripts.refresh   # force a run now (or locally: uv run python -m calorie_tracker.scripts.refresh)
docker compose exec redis redis-cli --raw get rollup:demo-uid:summary
```
Re-running over unchanged data writes nothing (digests match) — see the trace in `docs/EX3-notes.md`.

## Tests & CI
```bash
docker compose exec api pytest        # or, locally: cd backend && uv run pytest   (37 tests)
```
CI runs `uv run pytest` on every push/PR via `.github/workflows/ci.yml` (in-memory SQLite +
stubbed models, so it needs no DB/Redis/Firebase/AI secrets).

**Contract/fuzz testing (Schemathesis, manual).** Every route except `/health` needs an auth
token, so run it against the live dev stack with the dev `demo-token`:
```bash
uvx schemathesis run http://localhost:9000/openapi.json \
  -H 'Authorization: Bearer demo-token' --checks all
```

## Local LLM — run with no cloud API key (opt-in)
By default the agent uses the cloud providers from `.env` (Anthropic → Gemini → Groq → OpenRouter).
To run **fully offline** with a bundled open-source model instead, use the `local-llm` profile —
it starts Ollama and auto-pulls a small tool-capable model (`llama3.2:3b`), which becomes the
default until a user adds their own key (BYO keys always win):
```bash
cd backend && docker compose --profile local-llm up --build
# first run downloads ~2 GB into the sc_ollama volume; CPU inference is slow
docker compose ps                                  # …+ ollama (ollama-pull exits after the pull)
docker compose logs -f ollama-pull                 # watch the model download
```
Notes:
- Pick the model with `OLLAMA_MODEL` (must support tool-calling — the agent needs it). Gemma was
  considered but its tool-calling on Ollama is unreliable; `llama3.2:3b` / `qwen2.5:3b` work well.
- The api waits for the pull to finish before serving (first start is slower).
- Plain `docker compose up` (no profile) is unchanged — Ollama isn't started and stays last in the
  chain, so cloud keys are used as before.

## One-command demo
From the repo root (auto-starts a bare SQLite API if the stack isn't up):
```bash
bash scripts/demo.sh
```

## Tear down
```bash
docker compose down            # keep volumes (Postgres data survives)
docker compose down -v         # also drop the Postgres + node_modules volumes
```
