import json
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

import redis.asyncio as aioredis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..exceptions import HoldNotFoundError, RoomHeldError
from ..models import Hold, Room
from .availability_service import _date_range, release_dates, reserve_dates

logger = logging.getLogger(__name__)


async def check_hold(
    redis: aioredis.Redis,
    room_id: uuid.UUID,
    check_in: date,
    check_out: date,
    user_id: uuid.UUID,
) -> dict:
    """
    Quick Redis check for existing holds on the date range.
    Returns hold info if any date is held by a DIFFERENT user.
    """
    dates = _date_range(check_in, check_out)

    for d in dates:
        key = f"room_hold:{room_id}:{d.isoformat()}"
        hold_data = await redis.get(key)
        if hold_data:
            data = json.loads(hold_data)
            holder_id = uuid.UUID(data["userId"])
            if holder_id != user_id:
                return {
                    "held": True,
                    "holder_id": holder_id,
                    "hold_id": uuid.UUID(data["holdId"]),
                }
            else:
                # Same user already holds this — return existing hold
                return {
                    "held": True,
                    "holder_id": holder_id,
                    "hold_id": uuid.UUID(data["holdId"]),
                    "same_user": True,
                }

    return {"held": False, "holder_id": None, "hold_id": None}


async def create_hold(
    db: AsyncSession,
    redis: aioredis.Redis,
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    check_in: date,
    check_out: date,
) -> Hold:
    """
    Atomic hold creation:
    1. Reserve dates in DB (SELECT FOR UPDATE + decrement)
    2. Create Hold record in DB
    3. Set Redis keys with TTL
    """
    # Check if room exists and get price info
    result = await db.execute(select(Room).where(Room.id == room_id))
    room = result.scalar_one_or_none()
    if not room:
        from ..exceptions import RoomNotFoundError

        raise RoomNotFoundError(str(room_id))

    # Check for existing holds in Redis (fast path)
    hold_check = await check_hold(redis, room_id, check_in, check_out, user_id)
    if hold_check["held"] and not hold_check.get("same_user"):
        raise RoomHeldError(str(room_id), str(hold_check["holder_id"]))

    # Hold-per-user upsert: release any active hold the same user has on a different room
    existing_hold_result = await db.execute(
        select(Hold).where(
            and_(Hold.user_id == user_id, Hold.status == "active", Hold.room_id != room_id)
        )
    )
    old_hold = existing_hold_result.scalar_one_or_none()
    if old_hold:
        await release_hold(db, redis, old_hold.id)

    # Reserve dates (SELECT FOR UPDATE + decrement)
    await reserve_dates(db, room_id, check_in, check_out)

    # Create hold record in DB
    hold_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.hold_ttl)

    hold = Hold(
        id=hold_id,
        room_id=room_id,
        user_id=user_id,
        check_in=check_in,
        check_out=check_out,
        status="active",
        expires_at=expires_at,
        created_at=now,
    )
    db.add(hold)
    await db.flush()

    # Set Redis keys for each date in range
    dates = _date_range(check_in, check_out)
    hold_data = json.dumps(
        {
            "holdId": str(hold_id),
            "roomId": str(room_id),
            "userId": str(user_id),
            "checkIn": check_in.isoformat(),
            "checkOut": check_out.isoformat(),
            "createdAt": now.isoformat(),
        }
    )

    # Set per-date hold keys
    for d in dates:
        key = f"room_hold:{room_id}:{d.isoformat()}"
        await redis.set(key, hold_data, ex=settings.hold_ttl)

    # Set main hold key
    await redis.set(f"hold:{hold_id}", hold_data, ex=settings.hold_ttl)

    await db.commit()

    # Attach room info for response
    hold.price_per_night = float(room.price_per_night)
    hold.tax_rate = float(room.tax_rate)
    hold.room_type = room.room_type

    logger.info(f"Hold {hold_id} created for room {room_id}, expires at {expires_at}")
    return hold


async def release_hold(
    db: AsyncSession,
    redis: aioredis.Redis,
    hold_id: uuid.UUID,
) -> None:
    """Release a hold: restore inventory, update DB, delete Redis keys."""
    result = await db.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one_or_none()
    if not hold:
        raise HoldNotFoundError(str(hold_id))

    if hold.status != "active":
        logger.warning(f"Hold {hold_id} is already {hold.status}, skipping release")
        return

    # Restore inventory
    await release_dates(db, hold.room_id, hold.check_in, hold.check_out)

    # Update hold status
    hold.status = "expired"
    await db.flush()

    # Delete Redis keys
    dates = _date_range(hold.check_in, hold.check_out)
    for d in dates:
        await redis.delete(f"room_hold:{hold.room_id}:{d.isoformat()}")
    await redis.delete(f"hold:{hold_id}")

    await db.commit()
    logger.info(f"Hold {hold_id} released, inventory restored")


async def get_hold(
    db: AsyncSession,
    redis: aioredis.Redis,
    hold_id: uuid.UUID,
) -> dict:
    """Get hold status and remaining TTL."""
    result = await db.execute(select(Hold).where(Hold.id == hold_id))
    hold = result.scalar_one_or_none()
    if not hold:
        raise HoldNotFoundError(str(hold_id))

    ttl = await redis.ttl(f"hold:{hold_id}")

    return {
        "hold": hold,
        "ttl": ttl if ttl > 0 else 0,
    }
