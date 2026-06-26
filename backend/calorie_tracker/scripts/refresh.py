"""Async daily-rollup refresher (Session 09 deliverable).

Recomputes each user's per-day macro totals + current logging streak for a recent window and
caches the result in Redis so read paths (e.g. an insights dashboard) can serve a precomputed
snapshot instead of re-aggregating every diary row on each request.

It is built to the Session 09 brief:

* **Bounded concurrency** — at most `max_concurrency` users are processed at once
  (`asyncio.Semaphore`), so a large user base can't stampede the DB or Redis.
* **Retries** — each user's work is wrapped in `_with_retries` (exponential backoff), so a
  transient Redis/DB blip is retried instead of dropping that user from the run.
* **Redis-backed idempotency** — every cached key is paired with a sha256 digest of its payload.
  Re-running the refresher with unchanged data writes nothing (the digests match), so it is safe
  to run on a timer, by hand, or twice after a crash without duplicating work. This is also what
  makes the *retry* safe: a retried attempt simply skips the keys an earlier attempt already wrote.

Run it locally once Redis is up:

    cd backend
    uv run python -m calorie_tracker.scripts.refresh

It reads `REDIS_URL` / `DATABASE_URL` from the environment (same settings as the API) and exits
0 after logging a one-line summary. The process itself is one-shot (no internal daemon); the
`refresher` compose service runs it on a loop (`REFRESH_INTERVAL_SECONDS`, default hourly), and
you can also drive it from cron/launchd. Nothing in the request path depends on it (the insights
routes still compute live), so a stale or skipped run only means a slightly cold cache.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable, ContextManager, Protocol

from sqlmodel import Session, select

from ..config import get_settings
from ..models import FoodEntry, User, UserGoals
from ..services import nutrition as nut

logger = logging.getLogger(__name__)

# How long a cached rollup lives. Comfortably longer than a daily cadence so a missed run leaves
# yesterday's snapshot in place rather than an empty cache.
_DEFAULT_TTL_SECONDS = 36 * 60 * 60

SessionFactory = Callable[[], ContextManager[Session]]


class RedisLike(Protocol):
    """The tiny async Redis surface the refresher needs (real `redis.asyncio.Redis` satisfies it)."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ex: int | None = None) -> object: ...


@dataclass
class RefreshStats:
    users_processed: int = 0
    keys_written: int = 0
    keys_skipped: int = 0  # idempotent no-ops (payload unchanged since last run)
    retries: int = 0
    errors: int = 0
    user_uids: list[str] = field(default_factory=list)

    def __str__(self) -> str:  # one-line log summary
        return (
            f"users={self.users_processed} written={self.keys_written} "
            f"skipped(idempotent)={self.keys_skipped} retries={self.retries} errors={self.errors}"
        )


def _day_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _list_user_uids(session_factory: SessionFactory) -> list[str]:
    with session_factory() as session:
        rows = session.exec(select(User.uid)).all()
    return [r if isinstance(r, str) else r[0] for r in rows]


def compute_rollups(session: Session, uid: str, *, days: int, now: datetime) -> dict:
    """Pure read: aggregate `uid`'s last `days` days of diary into a JSON-serialisable rollup.

    Returns ``{"days": {<iso date>: {...}}, "streak": int, "generated_at": <iso>}``.
    """
    window_start = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    rows = session.exec(
        select(FoodEntry)
        .where(FoodEntry.user_uid == uid)
        .where(FoodEntry.eaten_at >= window_start)
    ).all()

    goals = session.get(UserGoals, uid)
    target_kcal = goals.daily_kcal if goals else None

    by_day: dict[str, list[FoodEntry]] = defaultdict(list)
    eaten_dates: set = set()
    for r in rows:
        d = _day_utc(r.eaten_at).date()
        by_day[d.isoformat()].append(r)
        eaten_dates.add(d)

    days_out: dict[str, dict] = {}
    for iso, day_rows in by_day.items():
        totals = nut.aggregate(day_rows)
        days_out[iso] = {
            "date": iso,
            "calories": int(totals["calories"]),
            "protein_g": round(totals["protein_g"], 1),
            "carb_g": round(totals["carb_g"], 1),
            "fat_g": round(totals["fat_g"], 1),
            "entries": len(day_rows),
            "target_kcal": target_kcal,
        }

    return {
        "days": days_out,
        "streak": nut.streak_from_dates(eaten_dates, today=now.date()),
        "generated_at": now.astimezone(timezone.utc).isoformat(),
    }


def _digest(payload: dict) -> tuple[str, str]:
    """Return ``(sha256_hexdigest, canonical_json_blob)`` for a payload."""
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), blob


async def _idempotent_set(redis: RedisLike, key: str, payload: dict, *, ttl: int) -> bool:
    """Write ``key`` only if its payload changed since last run. Returns True if written.

    The companion ``{key}:digest`` holds a sha256 of the last-written payload; when it already
    matches we skip both writes — that's the idempotency guarantee (and what makes retries safe).
    """
    digest, blob = _digest(payload)
    if await redis.get(f"{key}:digest") == digest:
        return False
    await redis.set(key, blob, ex=ttl)
    await redis.set(f"{key}:digest", digest, ex=ttl)
    return True


async def _with_retries(
    fn: Callable[[], Awaitable], *, attempts: int, base_delay: float, on_retry: Callable[[], None]
):
    """Run `fn`, retrying on any exception with exponential backoff. Re-raises the last error."""
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 — transient DB/Redis errors are retryable
            last_exc = exc
            if i < attempts - 1:
                on_retry()
                summary = " ".join(str(exc).split())[:120]
                logger.warning("attempt %d/%d failed (%s); retrying", i + 1, attempts, summary)
                if base_delay > 0:
                    await asyncio.sleep(base_delay * (2**i))
    assert last_exc is not None
    raise last_exc


async def refresh_user(
    redis: RedisLike,
    session_factory: SessionFactory,
    uid: str,
    *,
    days: int,
    now: datetime,
    ttl: int = _DEFAULT_TTL_SECONDS,
) -> tuple[int, int]:
    """Recompute + cache one user's rollups. Returns (keys_written, keys_skipped)."""
    # DB aggregation is sync SQLModel; run it off the event loop so concurrent users overlap.
    rollup = await asyncio.to_thread(_compute_in_session, session_factory, uid, days, now)

    written = skipped = 0
    for iso, day_payload in rollup["days"].items():
        if await _idempotent_set(redis, f"rollup:{uid}:{iso}", day_payload, ttl=ttl):
            written += 1
        else:
            skipped += 1

    summary_payload = {
        "uid": uid,
        "streak": rollup["streak"],
        "days_cached": sorted(rollup["days"].keys()),
        "generated_at": rollup["generated_at"],
    }
    if await _idempotent_set(redis, f"rollup:{uid}:summary", summary_payload, ttl=ttl):
        written += 1
    else:
        skipped += 1
    return written, skipped


def _compute_in_session(
    session_factory: SessionFactory, uid: str, days: int, now: datetime
) -> dict:
    with session_factory() as session:
        return compute_rollups(session, uid, days=days, now=now)


async def refresh_all(
    redis: RedisLike,
    session_factory: SessionFactory,
    *,
    days: int = 7,
    max_concurrency: int = 4,
    attempts: int = 3,
    retry_base_delay: float = 0.5,
    ttl: int = _DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> RefreshStats:
    """Refresh every user's rollups with bounded concurrency, retries and idempotent writes."""
    now = now or datetime.now(timezone.utc)
    uids = await asyncio.to_thread(_list_user_uids, session_factory)
    stats = RefreshStats(user_uids=list(uids))
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def _one(uid: str) -> None:
        async with sem:
            try:
                written, skipped = await _with_retries(
                    lambda: refresh_user(
                        redis, session_factory, uid, days=days, now=now, ttl=ttl
                    ),
                    attempts=attempts,
                    base_delay=retry_base_delay,
                    on_retry=lambda: _bump_retry(stats),
                )
            except Exception:  # noqa: BLE001 — one bad user shouldn't sink the whole run
                stats.errors += 1
                logger.exception("refresh failed for user %s", uid)
                return
            stats.users_processed += 1
            stats.keys_written += written
            stats.keys_skipped += skipped

    await asyncio.gather(*(_one(u) for u in uids))
    return stats


def _bump_retry(stats: RefreshStats) -> None:
    stats.retries += 1


async def _amain() -> None:
    from redis.asyncio import Redis

    from ..db import get_engine

    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5.0)
    try:
        await redis.ping()
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis unavailable at %s (%s) — refresh aborted.", settings.redis_url, exc)
        return

    def _factory() -> ContextManager[Session]:
        return Session(get_engine())

    stats = await refresh_all(redis, _factory)
    logger.info("refresh complete: %s", stats)
    try:
        await redis.aclose()
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    asyncio.run(_amain())


if __name__ == "__main__":
    main()
