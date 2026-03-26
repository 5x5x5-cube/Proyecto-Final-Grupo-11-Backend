"""Core booking creation — simple DB insert."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Booking
from ..schemas import BookingResponse, CreateBookingRequest, PriceBreakdown


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
    user_id: uuid.UUID,
    request: CreateBookingRequest,
) -> BookingResponse:
    """
    Simple booking creation: insert a confirmed booking record directly.
    The hold was already created by cart_service; prices are pre-calculated.
    """
    booking = Booking(
        user_id=user_id,
        hotel_id=request.hotel_id,
        room_id=request.room_id,
        hold_id=request.hold_id,
        check_in=request.check_in,
        check_out=request.check_out,
        guests=request.guests,
        status="confirmed",
        base_price=request.base_price,
        tax_amount=request.tax_amount,
        service_fee=request.service_fee,
        total_price=request.total_price,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return build_booking_response(booking)
