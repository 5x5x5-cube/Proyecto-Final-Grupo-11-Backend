"""
Async distributed Redis lock — ported from experiment's RedisLock.

Uses SET NX (atomic set-if-not-exists) with TTL for acquisition,
and a Lua script for atomic compare-and-delete on release.
"""

import asyncio
import logging
import uuid

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# Lua script: only delete the key if it still holds our value (prevents releasing someone else's lock)
RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class RedisLock:
    def __init__(self, redis_client: aioredis.Redis, lock_key: str, timeout: int = 10):
        self.redis_client = redis_client
        self.lock_key = lock_key
        self.timeout = timeout
        self.lock_value = str(uuid.uuid4())
        self.acquired = False

    async def acquire(self, retry_attempts: int = 3, retry_delay: float = 0.1) -> bool:
        for attempt in range(retry_attempts):
            acquired = await self.redis_client.set(
                self.lock_key,
                self.lock_value,
                nx=True,
                ex=self.timeout,
            )

            if acquired:
                self.acquired = True
                logger.info(f"Lock acquired: {self.lock_key} (attempt {attempt + 1})")
                return True

            if attempt < retry_attempts - 1:
                await asyncio.sleep(retry_delay * (2**attempt))

        logger.warning(f"Failed to acquire lock: {self.lock_key} after {retry_attempts} attempts")
        return False

    async def release(self) -> bool:
        if not self.acquired:
            return False

        try:
            result = await self.redis_client.eval(RELEASE_LUA, 1, self.lock_key, self.lock_value)
            if result:
                logger.info(f"Lock released: {self.lock_key}")
                self.acquired = False
                return True
            else:
                logger.warning(f"Lock already expired or owned by another process: {self.lock_key}")
                return False
        except Exception:
            logger.exception(f"Error releasing lock {self.lock_key}")
            return False

    async def __aenter__(self):
        if not await self.acquire():
            raise LockAcquisitionError(self.lock_key)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
        return False


class LockAcquisitionError(Exception):
    def __init__(self, lock_key: str):
        self.lock_key = lock_key
        super().__init__(f"Could not acquire lock: {lock_key}")


def create_booking_lock(
    redis_client: aioredis.Redis,
    room_id: str,
    check_in: str,
    check_out: str,
    timeout: int = 10,
) -> RedisLock:
    """Factory for creating a booking transaction lock."""
    lock_key = f"lock:booking:{room_id}:{check_in}:{check_out}"
    return RedisLock(redis_client, lock_key, timeout)
