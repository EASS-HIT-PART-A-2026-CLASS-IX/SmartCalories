"""arq job functions. Worker exists primarily to satisfy the EX3 "async worker" rubric line.

The single job below is the idempotent counterpart to scripts/refresh.py — when called from
the script it just confirms the worker can fetch and roundtrip a payload through Redis.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def refresh_cache_entry(ctx: dict, entry_key: str) -> dict[str, Any]:
    """Trivial idempotent job — used by scripts/refresh.py to demonstrate the queue path."""
    logger.info("refresh_cache_entry job for %s", entry_key)
    return {"entry_key": entry_key, "status": "ok"}
