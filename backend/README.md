# SmartCalories — backend

FastAPI + SQLModel + Alembic + a smolagents/LiteLLM chat agent. Python 3.12 /
[uv](https://docs.astral.sh/uv/).

Project-level documentation lives at `../README.md` and `../docs/EX3-notes.md`. This file is the
package-local readme that Hatchling picks up when building the wheel.

## Run
```bash
uv sync
cp .env.example .env                                       # set DATABASE_URL etc. (SQLite is the default)
# Postgres path: apply migrations. (SQLite quick-run: tables auto-create on startup.)
uv run alembic upgrade head
ENVIRONMENT=dev uv run uvicorn calorie_tracker.main:app --port 9000 --reload   # http://127.0.0.1:9000
uv run pytest                                              # 37 tests
```
Seed demo data via the dev endpoint (no standalone seed script):
`curl -s -X POST http://127.0.0.1:9000/auth/demo`

## Compose
```bash
docker compose up --build           # db (Postgres) + api :9000 + web :5173 + redis + refresher (all local)
```

## AI Assistance
Built with Claude Code; see the **AI Assistance** section of the root `../README.md` and the full
account in `../docs/EX3-notes.md` (prompts/decisions and how outputs were verified — `uv run
pytest`, `npm run build`, and `scripts/demo.sh`).
