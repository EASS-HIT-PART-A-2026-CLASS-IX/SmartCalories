# Compose runbook

The compose file is at `backend/compose.yaml` — a single self-contained dev stack. It brings up
four services: `db` (local **Postgres**), `api` (FastAPI + uvicorn `--reload` on :9000), `web`
(Vite dev server with HMR on :5173, reads `frontend/.env` live), and `redis` (rate-limit
middleware). Everything runs locally — **no external Neon or Redis Cloud needed**; the api points
at the in-compose Postgres + Redis containers regardless of the `DATABASE_URL`/`REDIS_URL` in
`.env` (those are only for non-Docker runs and for prod via `render.yaml`).

## Bring up the stack
```bash
cd backend
cp .env.example .env             # AI keys (ANTHROPIC/GEMINI/…) optional; DB + Redis come from compose
docker compose up --build -d
docker compose ps                # db · api · web · redis
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

## Tests
```bash
docker compose exec api pytest        # or, locally: cd backend && uv run pytest   (38 tests)
```

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
