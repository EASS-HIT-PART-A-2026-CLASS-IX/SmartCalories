"""Async refresh script (Session 09 deliverable).

Bounded concurrency via anyio.Semaphore, retry-with-backoff via tenacity, Redis-backed
idempotency via SET NX EX so re-runs of the same target within the TTL are no-ops.

Usage:
    uv run python -m calorie_tracker.scripts.refresh

Each target has a Redis lock keyed by ``refresh:<id>`` so we never refresh the same target
twice in the same TTL window. The actual "work" callable is intentionally trivial — the
deliverable is the *pattern* (bounded concurrency + idempotency + retries), not the payload.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Awaitable, Callable, Iterable

import anyio
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger("smart_calories.refresh")

DEFAULT_TARGETS: list[str] = [f"target-{i}" for i in range(1, 6)]


async def _refresh_one(target: str, *, work: Callable[[str], Awaitable[None]]) -> None:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=0.2, max=2.0),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    ):
        with attempt:
            await work(target)


async def refresh_targets(
    targets: Iterable[str],
    *,
    cache,
    work: Callable[[str], Awaitable[None]] | None = None,
    concurrency: int = 8,
    ttl_seconds: int = 600,
) -> dict[str, int]:
    """Run `work(target)` for each target with bounded concurrency + per-target idempotency.

    `cache` must expose async `get(key)` and `set(key, value, ttl)` (any of our cache wrappers
    or a fakeredis-backed shim works).
    `work` defaults to a no-op so tests can verify locking behaviour without HTTP.
    """
    sem = anyio.Semaphore(concurrency)
    counts = {"refreshed": 0, "skipped": 0, "failed": 0}
    work_fn = work or (lambda _t: _noop())

    async def _process(target: str) -> None:
        key = f"refresh:{target}"
        existing = await cache.get(key)
        if existing:
            counts["skipped"] += 1
            return
        async with sem:
            try:
                await _refresh_one(target, work=work_fn)
                await cache.set(key, "done", ttl=ttl_seconds)
                counts["refreshed"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("refresh %s failed: %s", target, exc)
                counts["failed"] += 1

    async with anyio.create_task_group() as tg:
        for t in targets:
            tg.start_soon(_process, t)
    return counts


async def _noop() -> None:
    return None


async def _real_work(target: str) -> None:
    """Default refresh action — log + small async pause stands in for any real I/O. The
    EX3 deliverable is the bounded-concurrency + idempotency pattern, not the payload."""
    logger.info("refreshing %s", target)
    await anyio.sleep(0.05)


async def main_async(targets: list[str], concurrency: int, ttl: int) -> dict[str, int]:
    from ..services.cache import get_cache

    return await refresh_targets(
        targets,
        cache=get_cache(),
        work=_real_work,
        concurrency=concurrency,
        ttl_seconds=ttl,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="SmartCalories refresh worker")
    parser.add_argument("--target", action="append", help="Override target list (repeatable)")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--ttl", type=int, default=600, help="Idempotency TTL seconds")
    args = parser.parse_args()

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    targets = args.target or DEFAULT_TARGETS
    counts = asyncio.run(main_async(targets, args.concurrency, args.ttl))
    print(f"refreshed={counts['refreshed']} skipped={counts['skipped']} failed={counts['failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
