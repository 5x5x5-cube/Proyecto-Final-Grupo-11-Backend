import asyncio
from unittest.mock import AsyncMock

import pytest

from app.redis_lock import LockAcquisitionError, RedisLock, create_booking_lock


async def test_acquire_success():
    redis = AsyncMock()
    redis.set.return_value = True

    lock = RedisLock(redis, "lock:test", timeout=10)
    result = await lock.acquire()

    assert result is True
    assert lock.acquired is True
    redis.set.assert_called_once()


async def test_acquire_failure_after_retries():
    redis = AsyncMock()
    redis.set.return_value = False

    lock = RedisLock(redis, "lock:test", timeout=10)
    result = await lock.acquire(retry_attempts=2, retry_delay=0.01)

    assert result is False
    assert lock.acquired is False
    assert redis.set.call_count == 2


async def test_release_success():
    redis = AsyncMock()
    redis.set.return_value = True
    redis.eval.return_value = 1

    lock = RedisLock(redis, "lock:test", timeout=10)
    await lock.acquire()
    result = await lock.release()

    assert result is True
    assert lock.acquired is False


async def test_release_without_acquire():
    redis = AsyncMock()
    lock = RedisLock(redis, "lock:test", timeout=10)
    result = await lock.release()

    assert result is False
    redis.eval.assert_not_called()


async def test_release_expired_lock():
    redis = AsyncMock()
    redis.set.return_value = True
    redis.eval.return_value = 0  # Lock was already expired/taken

    lock = RedisLock(redis, "lock:test", timeout=10)
    await lock.acquire()
    result = await lock.release()

    assert result is False


async def test_context_manager_success():
    redis = AsyncMock()
    redis.set.return_value = True
    redis.eval.return_value = 1

    lock = RedisLock(redis, "lock:test", timeout=10)
    async with lock:
        assert lock.acquired is True

    assert lock.acquired is False


async def test_context_manager_failure():
    redis = AsyncMock()
    redis.set.return_value = False

    lock = RedisLock(redis, "lock:test", timeout=10)
    with pytest.raises(LockAcquisitionError):
        async with lock:
            pass


async def test_create_booking_lock_key_format():
    redis = AsyncMock()
    lock = create_booking_lock(redis, "room-123", "2026-04-01", "2026-04-03", timeout=10)
    assert lock.lock_key == "lock:booking:room-123:2026-04-01:2026-04-03"
    assert lock.timeout == 10
