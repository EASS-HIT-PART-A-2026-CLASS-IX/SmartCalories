"""Tiny Redis cache wrapper. Fails open: if Redis is unavailable, calls become no-ops."""
from __future__ import annotations

import logging
from typing import Protocol


logger = logging.getLogger(__name__)


class AsyncCache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int = 3600) -> None: ...


class RedisCache:
    def __init__(self, redis_url: str | None) -> None:
        self._url = redis_url
        self._client = None
        self._tried_init = False

    async def _ensure(self) -> None:
        if self._tried_init:
            return
        self._tried_init = True
        if not self._url:
            return
        try:
            from redis.asyncio import Redis  # type: ignore[import-not-found]

            client = Redis.from_url(self._url, decode_responses=True, socket_timeout=2.0)
            await client.ping()
            self._client = client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable; cache disabled: %s", exc)
            self._client = None

    async def get(self, key: str) -> str | None:
        await self._ensure()
        if self._client is None:
            return None
        try:
            return await self._client.get(key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis get failed: %s", exc)
            return None

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        await self._ensure()
        if self._client is None:
            return
        try:
            await self._client.set(key, value, ex=ttl)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis set failed: %s", exc)


_cache: AsyncCache | None = None


def get_cache() -> AsyncCache:
    """FastAPI dependency. Override in tests for fakeredis or in-memory."""
    global _cache
    if _cache is None:
        from ..config import get_settings

        _cache = RedisCache(get_settings().redis_url)
    return _cache


def set_cache_for_tests(cache: AsyncCache) -> None:
    """Used by tests + bootstrap to inject a known cache."""
    global _cache
    _cache = cache
