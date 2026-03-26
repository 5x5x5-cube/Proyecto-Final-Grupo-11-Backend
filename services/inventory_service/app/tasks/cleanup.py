import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import and_, select

from ..config import settings
from ..database import async_session_factory
from ..models import Hold
from ..redis_client import get_redis
from ..services.availability_service import _date_range, release_dates

logger = logging.getLogger(__name__)


async def cleanup_expired_holds() -> int:
    """Find and clean up expired holds. Returns count of cleaned holds."""
    cleaned = 0
    async with async_session_factory() as db:
        result = await db.execute(
            select(Hold).where(
                and_(
                    Hold.status == "active",
                    Hold.expires_at < datetime.now(timezone.utc),
                )
            )
        )
        expired_holds = result.scalars().all()

        if not expired_holds:
            return 0

        redis = await get_redis()

        for hold in expired_holds:
            try:
                # Restore inventory
                await release_dates(db, hold.room_id, hold.check_in, hold.check_out)

                # Update hold status
                hold.status = "expired"

                # Clean up Redis keys (should already be expired via TTL, but belt-and-suspenders)
                dates = _date_range(hold.check_in, hold.check_out)
                for d in dates:
                    await redis.delete(f"room_hold:{hold.room_id}:{d.isoformat()}")
                await redis.delete(f"hold:{hold.id}")

                cleaned += 1
                logger.info(f"Cleaned up expired hold {hold.id} for room {hold.room_id}")
            except Exception:
                logger.exception(f"Error cleaning up hold {hold.id}")

        await db.commit()

    logger.info(f"Cleanup complete: {cleaned} expired holds processed")
    return cleaned


async def cleanup_expired_holds_loop() -> None:
    """Background loop that periodically cleans up expired holds."""
    logger.info(f"Starting hold cleanup loop (interval: {settings.cleanup_interval}s)")
    while True:
        try:
            await cleanup_expired_holds()
        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")
            break
        except Exception:
            logger.exception("Error in cleanup loop")
        await asyncio.sleep(settings.cleanup_interval)
