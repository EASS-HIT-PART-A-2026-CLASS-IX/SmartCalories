# SmartCalories — backend

FastAPI + SQLModel + Pydantic AI + arq + FastMCP. Python 3.12 / [uv](https://docs.astral.sh/uv/).

Project-level documentation lives at `../README.md` and `../.claude/`. This file is the
package-local readme that Hatchling picks up when building the wheel.

## Run
```bash
uv sync
cp .env.example .env                              # set DATABASE_URL, etc.
uv run alembic upgrade head
uv run python -m calorie_tracker.scripts.seed
uv run uvicorn calorie_tracker.main:app --reload  # http://127.0.0.1:8000
uv run pytest                                     # 59 tests
```

## Compose
```bash
docker compose up --build                         # api + worker + redis + web
```
