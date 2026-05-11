"""Unit tests for the fraud detection engine (HU4.7)."""

import time
import uuid
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.services.fraud_detector import (
    FraudResult,
    check_3ds_failures,
    check_duplicate,
    check_velocity,
    evaluate_transaction,
    record_3ds_failure,
    record_transaction,
    reset_3ds_failures,
)

USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
METHOD_ID = uuid.uuid4()
NOW = 1_700_000_000.0  # Fixed timestamp keeps assertions deterministic


def _fake_redis() -> AsyncMock:
    """Return an AsyncMock pre-configured with the Redis methods we use."""
    mock = AsyncMock()
    mock.zremrangebyscore = AsyncMock(return_value=0)
    mock.zscore = AsyncMock(return_value=None)
    mock.zcount = AsyncMock(return_value=0)
    mock.zadd = AsyncMock(return_value=1)
    mock.get = AsyncMock(return_value=None)
    mock.incr = AsyncMock(return_value=1)
    mock.delete = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    return mock


# ─── Duplicate detection ──────────────────────────────────────────────────


class TestCheckDuplicate:
    async def test_no_match_returns_false(self):
        redis = _fake_redis()
        redis.zscore.return_value = None
        assert await check_duplicate(redis, USER_ID, 100.0, METHOD_ID, now=NOW) is False

    async def test_recent_match_returns_true(self):
        redis = _fake_redis()
        # A score just inside the window
        redis.zscore.return_value = NOW - 10
        assert await check_duplicate(redis, USER_ID, 100.0, METHOD_ID, now=NOW) is True

    async def test_old_match_is_ignored(self):
        redis = _fake_redis()
        # A score older than the duplicate window — should be treated as no match
        redis.zscore.return_value = NOW - settings.fraud_duplicate_window_seconds - 1
        assert await check_duplicate(redis, USER_ID, 100.0, METHOD_ID, now=NOW) is False

    async def test_amount_rounding_keeps_fingerprint_stable(self):
        """100.00 and 100.001 must hash to the same fingerprint."""
        redis = _fake_redis()
        redis.zscore.return_value = NOW
        # Two checks with slightly different float noise must hit the same key
        await check_duplicate(redis, USER_ID, 100.00, METHOD_ID, now=NOW)
        await check_duplicate(redis, USER_ID, 100.001, METHOD_ID, now=NOW)
        first_fp = redis.zscore.call_args_list[0].args[1]
        second_fp = redis.zscore.call_args_list[1].args[1]
        assert first_fp == second_fp


# ─── Velocity detection ───────────────────────────────────────────────────


class TestCheckVelocity:
    async def test_below_threshold_returns_false(self):
        redis = _fake_redis()
        redis.zcount.return_value = settings.fraud_velocity_threshold - 1
        assert await check_velocity(redis, USER_ID, now=NOW) is False

    async def test_at_or_above_threshold_returns_true(self):
        redis = _fake_redis()
        redis.zcount.return_value = settings.fraud_velocity_threshold
        assert await check_velocity(redis, USER_ID, now=NOW) is True

    async def test_uses_correct_window(self):
        redis = _fake_redis()
        await check_velocity(redis, USER_ID, now=NOW)
        cutoff = redis.zcount.call_args.args[1]
        # Cutoff must equal now - velocity_window
        assert cutoff == NOW - settings.fraud_velocity_window_seconds


# ─── 3DS failure tracking ─────────────────────────────────────────────────


class TestCheck3DSFailures:
    async def test_no_counter_returns_false(self):
        redis = _fake_redis()
        redis.get.return_value = None
        assert await check_3ds_failures(redis, METHOD_ID) is False

    async def test_below_threshold_returns_false(self):
        redis = _fake_redis()
        redis.get.return_value = str(settings.fraud_3ds_max_failures - 1)
        assert await check_3ds_failures(redis, METHOD_ID) is False

    async def test_at_threshold_returns_true(self):
        redis = _fake_redis()
        redis.get.return_value = str(settings.fraud_3ds_max_failures)
        assert await check_3ds_failures(redis, METHOD_ID) is True

    async def test_corrupted_counter_returns_false(self):
        """If someone writes garbage into the counter we must not block legit users."""
        redis = _fake_redis()
        redis.get.return_value = "not-a-number"
        assert await check_3ds_failures(redis, METHOD_ID) is False


# ─── Recorders ────────────────────────────────────────────────────────────


class TestRecorders:
    async def test_record_transaction_writes_and_expires(self):
        redis = _fake_redis()
        await record_transaction(redis, USER_ID, 100.0, METHOD_ID, now=NOW)
        redis.zadd.assert_awaited_once()
        # Key includes the user_id
        key = redis.zadd.call_args.args[0]
        assert str(USER_ID) in key
        # Sorted set is trimmed to the history TTL window
        redis.zremrangebyscore.assert_awaited_once()
        redis.expire.assert_awaited_once_with(key, settings.fraud_history_ttl_seconds)

    async def test_record_3ds_failure_increments_and_extends_ttl(self):
        redis = _fake_redis()
        redis.incr.return_value = 2
        new_value = await record_3ds_failure(redis, METHOD_ID)
        assert new_value == 2
        redis.incr.assert_awaited_once()
        redis.expire.assert_awaited_once()

    async def test_reset_3ds_failures_deletes_counter(self):
        redis = _fake_redis()
        await reset_3ds_failures(redis, METHOD_ID)
        redis.delete.assert_awaited_once()


# ─── Orchestrator ─────────────────────────────────────────────────────────


class TestEvaluateTransaction:
    async def test_clean_transaction_returns_none(self):
        redis = _fake_redis()
        result = await evaluate_transaction(redis, USER_ID, 100.0, METHOD_ID, now=NOW)
        assert result is None

    async def test_duplicate_takes_precedence(self):
        redis = _fake_redis()
        redis.zscore.return_value = NOW - 5  # within duplicate window
        result = await evaluate_transaction(redis, USER_ID, 100.0, METHOD_ID, now=NOW)
        assert isinstance(result, FraudResult)
        assert result.alert_type == "duplicate"
        # Velocity check is never invoked once duplicate fires
        redis.zcount.assert_not_called()

    async def test_velocity_fires_when_no_duplicate(self):
        redis = _fake_redis()
        redis.zscore.return_value = None  # no duplicate
        redis.zcount.return_value = settings.fraud_velocity_threshold
        result = await evaluate_transaction(redis, USER_ID, 100.0, METHOD_ID, now=NOW)
        assert isinstance(result, FraudResult)
        assert result.alert_type == "velocity"

    async def test_3ds_fires_last(self):
        redis = _fake_redis()
        redis.zscore.return_value = None
        redis.zcount.return_value = 0
        redis.get.return_value = str(settings.fraud_3ds_max_failures)
        result = await evaluate_transaction(redis, USER_ID, 100.0, METHOD_ID, now=NOW)
        assert isinstance(result, FraudResult)
        assert result.alert_type == "threed_secure_failed"


# ─── Integration smoke (still mocked) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_record_and_evaluate_uses_real_clock_if_now_is_omitted():
    """When `now` is not passed, the helpers use time.time() — sanity check."""
    redis = _fake_redis()
    # We just check that nothing blows up when `now` is implicit
    await record_transaction(redis, USER_ID, 100.0, METHOD_ID)
    assert redis.zadd.await_count == 1
    # And that the score passed to zadd is close to "now"
    score_map = redis.zadd.call_args.args[1]
    score = next(iter(score_map.values()))
    assert abs(score - time.time()) < 5
