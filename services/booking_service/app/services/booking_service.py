"""Core booking creation orchestration."""

import logging
import uuid
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..exceptions import InventoryServiceError
from ..models import Booking
from ..redis_lock import LockAcquisitionError, create_booking_lock
from ..schemas import BookingResponse, CreateBookingRequest, PriceBreakdown
from . import inventory_client

logger = logging.getLogger(__name__)


def build_booking_response(
    booking: Booking,
    price_breakdown: PriceBreakdown | None = None,
    hold_expires_at: datetime | None = None,
) -> BookingResponse:
    """Build a BookingResponse from an ORM Booking instance."""
    return BookingResponse(
        id=booking.id,
        code=booking.code,
        userId=booking.user_id,
        hotelId=booking.hotel_id,
        roomId=booking.room_id,
        holdId=booking.hold_id,
        checkIn=booking.check_in,
        checkOut=booking.check_out,
        guests=booking.guests,
        status=booking.status,
        totalPrice=float(booking.total_price),
        currency=booking.currency,
        priceBreakdown=price_breakdown,
        holdExpiresAt=hold_expires_at,
        createdAt=booking.created_at,
    )


async def create_booking(
    db: AsyncSession,
    redis: aioredis.Redis,
    request: CreateBookingRequest,
) -> BookingResponse:
    """
    Full booking creation flow:
    1. Pre-check holds — if same user already has a hold, return existing booking (idempotent)
    2. If held by another user, return 409
    3. Acquire transaction lock (Redis SET NX, 10s TTL)
    4. Create hold via inventory_service (SELECT FOR UPDATE + 15-min Redis TTL)
    5. Calculate price breakdown
    6. Create booking record (status=pending)
    7. Release lock
    8. Return booking with hold expiration
    """
    # 1. Quick pre-check: is the room already held?
    hold_check = await inventory_client.check_hold(
        room_id=request.room_id,
        check_in=request.check_in,
        check_out=request.check_out,
        user_id=request.user_id,
    )

    # Idempotent: same user already holds this room → return existing booking
    if hold_check.get("held") and hold_check.get("same_user"):
        hold_id = uuid.UUID(str(hold_check["hold_id"]))
        result = await db.execute(
            select(Booking).where(and_(Booking.hold_id == hold_id, Booking.status == "pending"))
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"Idempotent return: booking {existing.code} for hold {hold_id}")
            return build_booking_response(existing)
        # Edge case: hold exists but booking record missing — proceed to create

    # 2. Held by another user → 409
    if hold_check.get("held") and not hold_check.get("same_user"):
        raise InventoryServiceError("Room is being processed by another user", status_code=409)

    # 3. Acquire short-lived transaction lock
    lock = create_booking_lock(
        redis_client=redis,
        room_id=str(request.room_id),
        check_in=request.check_in.isoformat(),
        check_out=request.check_out.isoformat(),
        timeout=settings.lock_timeout,
    )

    hold_data = None
    try:
        async with lock:
            # 4. Create hold via inventory_service
            hold_data = await inventory_client.create_hold(
                room_id=request.room_id,
                user_id=request.user_id,
                check_in=request.check_in,
                check_out=request.check_out,
            )

            hold_id = uuid.UUID(hold_data["id"])
            price_per_night = float(hold_data.get("price_per_night", 0))
            tax_rate = float(hold_data.get("tax_rate", 0.19))
            expires_at = hold_data.get("expires_at")

            # 5. Calculate price breakdown
            nights = (request.check_out - request.check_in).days
            base_price = price_per_night * nights
            vat = round(base_price * tax_rate, 2)
            service_fee = 0
            total_price = round(base_price + vat + service_fee, 2)

            # 6. Create booking record
            booking = Booking(
                user_id=request.user_id,
                hotel_id=request.hotel_id,
                room_id=request.room_id,
                hold_id=hold_id,
                check_in=request.check_in,
                check_out=request.check_out,
                guests=request.guests,
                status="pending",
                base_price=base_price,
                tax_amount=vat,
                service_fee=service_fee,
                total_price=total_price,
                currency="COP",
            )
            db.add(booking)
            await db.commit()
            await db.refresh(booking)

    except LockAcquisitionError:
        raise InventoryServiceError("Server busy, please try again", status_code=503)
    except InventoryServiceError:
        raise
    except Exception:
        # Compensation: release hold if booking DB write failed
        if hold_data:
            logger.warning(f"Compensating: releasing hold {hold_data['id']}")
            await inventory_client.release_hold(uuid.UUID(hold_data["id"]))
        raise

    # 8. Build response
    price_breakdown = PriceBreakdown(
        pricePerNight=price_per_night,
        nights=nights,
        basePrice=base_price,
        vat=vat,
        serviceFee=service_fee,
        totalPrice=total_price,
        currency="COP",
    )

    return build_booking_response(
        booking,
        price_breakdown=price_breakdown,
        hold_expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
    )
