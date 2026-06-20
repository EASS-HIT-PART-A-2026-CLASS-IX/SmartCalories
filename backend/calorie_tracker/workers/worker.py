"""arq WorkerSettings entrypoint. Run with `arq calorie_tracker.workers.worker.WorkerSettings`."""
from __future__ import annotations

from arq.connections import RedisSettings

from ..config import get_settings
from .jobs import refresh_cache_entry


def _redis_settings() -> RedisSettings:
    url = get_settings().redis_url
    return RedisSettings.from_dsn(url)


class WorkerSettings:
    redis_settings = _redis_settings()
    functions = [refresh_cache_entry]
    job_timeout = 300
    keep_result = 3600
    max_jobs = 4
