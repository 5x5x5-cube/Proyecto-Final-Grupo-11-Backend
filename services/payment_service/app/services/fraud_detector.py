"""Fraud detection engine (HU4.7).

Stateless helpers + a single `evaluate_transaction` orchestrator. State
lives entirely in Redis so the engine can scale horizontally with the
payment_service replicas.

Rules:
  1. Duplicate     — same (user, amount, method) within W_DUP seconds.
  2. Velocity      — more than N transactions for the same user within
                     W_VEL seconds.
  3. 3DS failures  — N consecutive 3DS failures for the same payment method.

Redis key layout (single sorted-set per user keeps both #1 and #2 cheap):
  fraud:user_tx:{user_id}      ZSET  score=unix_ts, member=fingerprint
  fraud:3ds:{method_id}        STRING counter (with TTL block window)
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis

from ..config import settings

# ── Result type ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class FraudResult:
    """Outcome of a fraud check that was triggered."""

    alert_type: str  # "duplicate" | "velocity" | "threed_secure_failed"
    triggered_reason: str
    severity: str = "high"


# ── Key builders ────────────────────────────────────────────────────────────


def _user_tx_key(user_id: uuid.UUID) -> str:
    return f"fraud:user_tx:{user_id}"


def _3ds_key(method_id: uuid.UUID) -> str:
    return f"fraud:3ds:{method_id}"


def _fingerprint(user_id: uuid.UUID, amount: float, method_id: uuid.UUID) -> str:
    """Stable hash used as the sorted-set member for duplicate detection.

    Hashing keeps the member compact and avoids any chance of leaking
    amounts via the Redis key space. Amount is rounded to 2 decimals so
    floating-point noise does not break duplicate matches.
    """
    raw = f"{user_id}:{round(amount, 2)}:{method_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Rules ───────────────────────────────────────────────────────────────────


async def check_duplicate(
    redis: Redis,
    user_id: uuid.UUID,
    amount: float,
    method_id: uuid.UUID,
    *,
    now: float | None = None,
) -> bool:
    """True if a transaction with the same fingerprint exists within the window."""
    ts = now if now is not None else time.time()
    cutoff = ts - settings.fraud_duplicate_window_seconds
    fp = _fingerprint(user_id, amount, method_id)
    key = _user_tx_key(user_id)

    # Drop anything older than the duplicate window first so the next ZSCORE
    # call doesn't accidentally match a transaction that's outside it.
    await redis.zremrangebyscore(key, 0, cutoff)
    score = await redis.zscore(key, fp)
    return score is not None and float(score) >= cutoff


async def check_velocity(
    redis: Redis,
    user_id: uuid.UUID,
    *,
    now: float | None = None,
) -> bool:
    """True if the user exceeded the velocity threshold in the velocity window."""
    ts = now if now is not None else time.time()
    cutoff = ts - settings.fraud_velocity_window_seconds
    key = _user_tx_key(user_id)
    count = await redis.zcount(key, cutoff, "+inf")
    return count >= settings.fraud_velocity_threshold


async def check_3ds_failures(redis: Redis, method_id: uuid.UUID) -> bool:
    """True if 3DS consecutive failures for this method reached the threshold."""
    key = _3ds_key(method_id)
    raw = await redis.get(key)
    if raw is None:
        return False
    try:
        return int(raw) >= settings.fraud_3ds_max_failures
    except ValueError:
        # Corrupted counter — treat as not failed to avoid blocking legit users
        return False


# ── Recorders ───────────────────────────────────────────────────────────────


async def record_transaction(
    redis: Redis,
    user_id: uuid.UUID,
    amount: float,
    method_id: uuid.UUID,
    *,
    now: float | None = None,
) -> None:
    """Add a transaction fingerprint to the user's recent history."""
    ts = now if now is not None else time.time()
    fp = _fingerprint(user_id, amount, method_id)
    key = _user_tx_key(user_id)
    await redis.zadd(key, {fp: ts})
    # Keep the sorted set bounded — anything older than the velocity window
    # is irrelevant for both duplicate AND velocity checks.
    await redis.zremrangebyscore(key, 0, ts - settings.fraud_history_ttl_seconds)
    await redis.expire(key, settings.fraud_history_ttl_seconds)


async def record_3ds_failure(redis: Redis, method_id: uuid.UUID) -> int:
    """Increment the 3DS failure counter for this method. Returns new value."""
    key = _3ds_key(method_id)
    new_value = await redis.incr(key)
    # Refresh the TTL on every failure so a string of attempts keeps the
    # counter alive long enough to hit the threshold.
    await redis.expire(key, settings.fraud_3ds_block_seconds)
    return int(new_value)


async def reset_3ds_failures(redis: Redis, method_id: uuid.UUID) -> None:
    """Clear the 3DS counter — call after a successful 3DS validation."""
    await redis.delete(_3ds_key(method_id))


# ── Orchestrator ────────────────────────────────────────────────────────────


async def evaluate_transaction(
    redis: Redis,
    user_id: uuid.UUID,
    amount: float,
    method_id: uuid.UUID,
    *,
    now: float | None = None,
) -> FraudResult | None:
    """Run all rules in order; return the first triggered or None if clean.

    Rule order matters: duplicate is the cheapest and most specific, so it
    runs first. 3DS failures are independent of the user's recent history,
    so they run last.
    """
    if await check_duplicate(redis, user_id, amount, method_id, now=now):
        return FraudResult(
            alert_type="duplicate",
            triggered_reason=(
                f"Duplicate transaction within {settings.fraud_duplicate_window_seconds}s "
                "(same user, amount and method)"
            ),
        )

    if await check_velocity(redis, user_id, now=now):
        return FraudResult(
            alert_type="velocity",
            triggered_reason=(
                f"More than {settings.fraud_velocity_threshold} transactions "
                f"within {settings.fraud_velocity_window_seconds}s for the same user"
            ),
        )

    if await check_3ds_failures(redis, method_id):
        return FraudResult(
            alert_type="threed_secure_failed",
            triggered_reason=(
                f"More than {settings.fraud_3ds_max_failures} consecutive "
                "3D Secure failures for the payment method"
            ),
        )

    return None
