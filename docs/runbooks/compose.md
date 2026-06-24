# Compose runbook

The compose file is at `backend/compose.yaml` — a single dev-friendly stack (no separate prod
override). It brings up three services: `api` (FastAPI + uvicorn `--reload` on :9000), `web`
(Vite dev server with HMR on :5173, reads `frontend/.env` live), and `redis`. Redis is gated
behind the `local-redis` profile — in non-dev you point `REDIS_URL` at a managed instance
instead. Redis is used by exactly one thing: the rate-limit middleware.

## Bring up the stack
```bash
cd backend
cp .env.example .env             # set DATABASE_URL (Neon) — or leave the SQLite default for a quick run
                                 # AI keys (GEMINI_API_KEY / GROQ_API_KEY / …) are optional
docker compose --profile local-redis up --build -d
docker compose ps                # api · web · redis
docker compose logs -f api
```

## Verify the stack
```bash
curl -s localhost:9000/health                        # {"status":"ok","app":"SmartCalories"}
curl -s localhost:9000/health/ready                  # {"status":"ready"}
curl -s -D - -o /dev/null localhost:9000/health | grep -i ratelimit   # X-RateLimit-* headers (need Redis up)
docker compose exec redis redis-cli ping             # PONG
```
> The rate limiter **falls open** when Redis is unreachable, so the `X-RateLimit-*` headers only
> appear when the app can actually reach Redis.
>
> ⚠️ **Gotcha:** if `.env` has `REDIS_URL` pointing at a *managed* host (e.g. Redis Cloud) **and**
> you run with `--profile local-redis`, the local `redis` container spins up healthy but the app
> still dials the managed host — and if that host isn't reachable from inside the container the
> limiter silently falls open (no headers). For a self-contained local stack, set
> `REDIS_URL=redis://redis:6379/0` (or just leave it unset — that's the compose default).

## Database & seed
On startup the API calls `init_db()`, which creates tables **only for SQLite** (a dev/test
convenience). The Postgres (Neon) schema is owned solely by Alembic — the compose `api` command
runs `alembic upgrade head` before launching uvicorn:
```bash
docker compose exec api alembic upgrade head   # usually a no-op; runs automatically on boot
```
Seed demo data (no separate seed script — it's an endpoint, dev-only):
```bash
# rich 30-day dataset for the demo user; returns the dev `demo-token`
curl -s -X POST localhost:9000/auth/demo | python3 -m json.tool
```
Then drive the API as that user with `Authorization: Bearer demo-token`, e.g.:
```bash
curl -s localhost:9000/diary/today -H 'Authorization: Bearer demo-token' | python3 -m json.tool
```

## Tests
```bash
docker compose exec api pytest        # or, locally: cd backend && uv run pytest   (38 tests)
```

## One-command demo
From the repo root (auto-starts a bare API if the stack isn't up):
```bash
bash scripts/demo.sh
```

## Tear down
```bash
docker compose --profile local-redis down       # keep volumes
docker compose --profile local-redis down -v    # also drop redis state + uploads
```
