"""Redis token-bucket rate limiter as a Starlette middleware.

Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` on every response.
Falls open when Redis is unavailable so local dev keeps working without a Redis service.
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, per_minute: int | None = None) -> None:
        super().__init__(app)
        self.per_minute = per_minute or get_settings().rate_limit_per_min
        self._client = None
        self._tried = False

    async def _ensure_redis(self) -> None:
        if self._tried:
            return
        self._tried = True
        try:
            from redis.asyncio import Redis  # type: ignore[import-not-found]

            client = Redis.from_url(get_settings().redis_url, decode_responses=True, socket_timeout=2.0)
            await client.ping()
            self._client = client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rate limit Redis unavailable: %s", exc)
            self._client = None

    def _bucket_key(self, request: Request) -> str:
        ident = request.headers.get("authorization") or request.client.host if request.client else "anon"
        # Hash so we don't store full tokens
        return f"rl:{abs(hash(ident)) % (10**12)}"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        await self._ensure_redis()
        if self._client is None:
            return await call_next(request)
        key = self._bucket_key(request)
        window_start = int(time.time() // 60) * 60
        bucket_key = f"{key}:{window_start}"
        try:
            count = await self._client.incr(bucket_key)
            if count == 1:
                await self._client.expire(bucket_key, 65)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate limit redis error: %s", exc)
            return await call_next(request)

        remaining = max(0, self.per_minute - count)
        reset = window_start + 60

        if count > self.per_minute:
            return Response(
                content='{"detail":"rate limited"}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "X-RateLimit-Limit": str(self.per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                    "Retry-After": str(reset - int(time.time())),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response
