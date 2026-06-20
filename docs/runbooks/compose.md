# Compose runbook

```bash
cd backend
cp .env.example .env             # fill DATABASE_URL (Neon), GEMINI_API_KEY (optional)
docker compose up --build -d
docker compose ps
docker compose logs -f api
```

## Verify the stack
```bash
curl -s localhost:8000/health/ready                 # {"status":"ready"}
curl -sI localhost:8000/health | grep -i ratelimit  # X-RateLimit-* headers present
docker compose exec redis redis-cli ping            # PONG
```

## Run migrations + seed (api container)
```bash
docker compose exec api alembic upgrade head
docker compose exec api python -m calorie_tracker.scripts.seed
```

## Run the async refresher
```bash
docker compose exec api python -m calorie_tracker.scripts.refresh
docker compose exec api python -m calorie_tracker.scripts.refresh    # second run → all skipped
```

## Generate a weekly report from the CLI
```bash
docker compose exec api python -c "
import asyncio
from sqlmodel import Session
from calorie_tracker.db import get_engine
from calorie_tracker.services.reports import generate_report
async def go():
    with Session(get_engine()) as s:
        job = await generate_report(s, 'demo-uid-0001')
        print(job.model_dump())
asyncio.run(go())
"
```

## Tear down
```bash
docker compose down                # keep volumes
docker compose down -v             # also drop redis state + uploads
```
