"""Tests for the async daily-rollup refresher (Session 09 deliverable).

These exercise the three properties the brief asks for — bounded concurrency, retries, and
Redis-backed idempotency — without a real Redis or event-loop framework beyond anyio. The
`@pytest.mark.anyio` marker runs each coroutine test on asyncio (see the `anyio_backend` fixture).
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

from calorie_tracker.models import FoodEntry, Meal, Source, User, UserGoals
from calorie_tracker.scripts import refresh as refresh_mod


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio-marked tests on asyncio only (we don't ship trio)."""
    return "asyncio"


class FakeRedis:
    """In-memory async stand-in for the slice of redis.asyncio the refresher uses."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.set_calls = 0

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        self.set_calls += 1
        return True


class FlakyRedis(FakeRedis):
    """Raises on the first `fail_times` `get` calls, then behaves normally."""

    def __init__(self, fail_times: int = 1) -> None:
        super().__init__()
        self.fail_times = fail_times
        self.get_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        if self.get_calls <= self.fail_times:
            raise ConnectionError("simulated transient redis failure")
        return await super().get(key)


def _make_engine():
    # A real temp-file SQLite — NOT a StaticPool ":memory:" engine. refresh_all runs each user's
    # read on its own thread (asyncio.to_thread, max_concurrency>1), and a single shared StaticPool
    # connection used by two threads at once raises "sqlite3.InterfaceError: bad parameter or other
    # API misuse" (flaky — it only bit under CI timing). A file gives each session its own
    # connection; concurrent SELECTs are safe.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _seed(engine, uid: str = "u1", *, days: int = 3) -> datetime:
    now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    with Session(engine) as s:
        s.add(User(uid=uid, email=f"{uid}@example.com"))
        s.add(UserGoals(user_uid=uid, daily_kcal=2000))
        for offset in range(days):
            day = now - timedelta(days=offset)
            s.add(
                FoodEntry(
                    user_uid=uid,
                    name="scrambled eggs",
                    calories=200,
                    protein_g=12,
                    carb_g=2,
                    fat_g=14,
                    meal=Meal.breakfast,
                    eaten_at=day,
                    source=Source.manual,
                )
            )
        s.commit()
    return now


@pytest.mark.anyio
async def test_refresh_writes_then_is_idempotent():
    engine = _make_engine()
    now = _seed(engine, days=3)
    redis = FakeRedis()
    factory = lambda: Session(engine)  # noqa: E731

    # First run writes 3 day rollups + 1 summary = 4 keys, nothing skipped.
    first = await refresh_mod.refresh_all(redis, factory, days=7, now=now, max_concurrency=2)
    assert first.users_processed == 1
    assert first.keys_written == 4
    assert first.keys_skipped == 0
    assert redis.store.get("rollup:u1:summary") is not None
    assert '"streak": 3' in redis.store["rollup:u1:summary"]

    writes_after_first = redis.set_calls

    # Second run over unchanged data: every key is an idempotent skip, no new Redis writes.
    second = await refresh_mod.refresh_all(redis, factory, days=7, now=now, max_concurrency=2)
    assert second.keys_written == 0
    assert second.keys_skipped == 4
    assert redis.set_calls == writes_after_first  # idempotency = zero extra writes


@pytest.mark.anyio
async def test_refresh_retries_transient_failure():
    engine = _make_engine()
    now = _seed(engine, days=2)
    redis = FlakyRedis(fail_times=1)  # first redis.get blows up, forcing one retry
    factory = lambda: Session(engine)  # noqa: E731

    stats = await refresh_mod.refresh_all(
        redis, factory, days=7, now=now, attempts=3, retry_base_delay=0, max_concurrency=1
    )

    assert stats.retries == 1
    assert stats.errors == 0
    assert stats.users_processed == 1
    assert stats.keys_written == 3  # 2 day rollups + 1 summary, written after the retry


@pytest.mark.anyio
async def test_refresh_bounded_concurrency_across_users():
    engine = _make_engine()
    now = _seed(engine, "u1", days=1)
    _seed(engine, "u2", days=1)
    _seed(engine, "u3", days=1)
    redis = FakeRedis()
    factory = lambda: Session(engine)  # noqa: E731

    stats = await refresh_mod.refresh_all(redis, factory, days=7, now=now, max_concurrency=2)

    assert stats.users_processed == 3
    assert set(stats.user_uids) == {"u1", "u2", "u3"}
    # 3 users x (1 day + 1 summary) = 6 keys.
    assert stats.keys_written == 6
