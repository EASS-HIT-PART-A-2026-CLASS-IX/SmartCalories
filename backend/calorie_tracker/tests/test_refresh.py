from __future__ import annotations

import pytest

from calorie_tracker.scripts.refresh import refresh_targets


class _MemCache:
    def __init__(self):
        self._d: dict[str, str] = {}

    async def get(self, key):
        return self._d.get(key)

    async def set(self, key, value, ttl=3600):
        self._d[key] = value


@pytest.mark.anyio
async def test_refresh_idempotency() -> None:
    cache = _MemCache()
    calls: list[str] = []

    async def work(t: str) -> None:
        calls.append(t)

    targets = ["a", "b", "c"]

    counts1 = await refresh_targets(targets, cache=cache, work=work, concurrency=2, ttl_seconds=60)
    assert counts1 == {"refreshed": 3, "skipped": 0, "failed": 0}
    assert sorted(calls) == ["a", "b", "c"]

    # Second run within TTL: every target is locked → all skipped, no extra work calls
    counts2 = await refresh_targets(targets, cache=cache, work=work, concurrency=2, ttl_seconds=60)
    assert counts2 == {"refreshed": 0, "skipped": 3, "failed": 0}
    assert sorted(calls) == ["a", "b", "c"]


@pytest.mark.anyio
async def test_refresh_retries_on_transient_error() -> None:
    cache = _MemCache()
    state = {"calls": 0}

    async def flaky(t: str) -> None:
        state["calls"] += 1
        if state["calls"] < 3:
            raise RuntimeError("transient")

    counts = await refresh_targets(["x"], cache=cache, work=flaky, concurrency=1, ttl_seconds=60)
    assert counts == {"refreshed": 1, "skipped": 0, "failed": 0}
    assert state["calls"] == 3


@pytest.mark.anyio
async def test_refresh_records_permanent_failures() -> None:
    cache = _MemCache()

    async def always_fail(_t: str) -> None:
        raise RuntimeError("nope")

    counts = await refresh_targets(["a", "b"], cache=cache, work=always_fail, concurrency=2, ttl_seconds=60)
    assert counts["failed"] == 2
    assert counts["refreshed"] == 0


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
