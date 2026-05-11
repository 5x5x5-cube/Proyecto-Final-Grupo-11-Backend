"""Async Redis client used by the fraud detector (HU4.7).

Kept on its own module so the fraud detector — and any future caller — can
share a single connection pool. The instance is lazily created on first call
so import-time of the application stays fast.
"""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis, from_url

from .config import settings

_redis: Optional[Redis] = None


async def get_redis() -> Redis:
    """Return a process-wide async Redis client.

    The first call builds a connection pool from `settings.redis_url`;
    subsequent calls reuse it. `decode_responses=True` keeps test
    assertions readable (we get `str` back, not `bytes`).
    """
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Tear down the shared client — call from FastAPI's lifespan shutdown."""
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None
