import uuid
from datetime import date, datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..exceptions import BookingNotFoundError
from ..models import Booking
from ..schemas import BookingListResponse, BookingResponse, CreateBookingRequest, QRCodeResponse
from ..services.booking_service import create_booking, enrich_booking_responses
from ..services.cancellation_policy import calculate_refund_percentage, days_until_check_in
from ..services.payment_client import PaymentServiceError, request_refund
from ..services.sns_publisher import sns_publisher

router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])


def get_user_id(request: Request) -> uuid.UUID:
    """Extract and validate the X-User-Id header; return 401 if missing or invalid."""
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-User-Id header is not a valid UUID")


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking_endpoint(
    request: CreateBookingRequest,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await create_booking(db=db, user_id=user_id, request=request)


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    user_id: uuid.UUID = Depends(get_user_id),
    status: str | None = Query(None),
    timeframe: str | None = Query(None, pattern="^(active|past)$"),
    payment_id: uuid.UUID | None = Query(None, alias="paymentId"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    query = select(Booking).where(Booking.user_id == user_id)
    count_query = select(func.count()).select_from(Booking).where(Booking.user_id == user_id)

    if status:
        query = query.where(Booking.status == status)
        count_query = count_query.where(Booking.status == status)

    today = date.today()
    if timeframe == "active":
        query = query.where(Booking.check_out >= today, Booking.status.notin_(["cancelled"]))
        count_query = count_query.where(
            Booking.check_out >= today, Booking.status.notin_(["cancelled"])
        )
    elif timeframe == "past":
        query = query.where(Booking.check_out < today)
        count_query = count_query.where(Booking.check_out < today)

    if payment_id:
        query = query.where(Booking.payment_id == payment_id)
        count_query = count_query.where(Booking.payment_id == payment_id)

    query = query.order_by(Booking.created_at.desc())
    query = query.offset((page - 1) * limit).limit(limit)

    result = await db.execute(query)
    bookings = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    from ..services.booking_service import build_booking_response

    responses = [build_booking_response(b) for b in bookings]
    await enrich_booking_responses(responses, bookings)

    return BookingListResponse(
        data=responses,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_detail(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from ..services.booking_service import build_booking_response

    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise BookingNotFoundError(str(booking_id))
    response = build_booking_response(booking)
    await enrich_booking_responses([response], [booking])
    return response


@router.get("/{booking_id}/qr", response_model=QRCodeResponse)
async def get_booking_qr(
    booking_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a QR code token for a confirmed booking.

    The QR code contains a signed JWT with booking information that can be
    presented at hotel reception for check-in.

    Requirements:
    - Booking must belong to the authenticated user
    - Booking must be in 'confirmed' status
    - Check-in date must be within ±3 days from today
    """
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="You don't have permission to access this booking"
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=400,
            detail=f"QR code can only be generated for confirmed bookings. Current status: {booking.status}",
        )

    # Verify check-in date is within valid range (±3 days)
    today = datetime.now(timezone.utc).date()
    days_until_checkin = (booking.check_in - today).days

    if days_until_checkin < -3 or days_until_checkin > 3:
        raise HTTPException(
            status_code=400,
            detail="QR code can only be generated within 3 days before or after check-in date",
        )

    # Generate JWT token
    expiration = datetime.now(timezone.utc) + timedelta(days=settings.jwt_qr_expiration_days)
    payload = {
        "booking_id": str(booking.id),
        "user_id": str(booking.user_id),
        "guest_name": booking.guest_name or "Guest",
        "hotel_id": str(booking.hotel_id),
        "check_in": booking.check_in.isoformat(),
        "check_out": booking.check_out.isoformat(),
        "exp": expiration,
        "iat": datetime.now(timezone.utc),
    }

    qr_token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    return QRCodeResponse(
        qrCode=qr_token, bookingId=booking.id, guestName=booking.guest_name or "Guest"
    )


@router.post("/{booking_id}/cancel", status_code=200)
async def cancel_booking(
    booking_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel an active booking and apply the refund policy (HU4.3).

    Flow:
    1. Validate ownership and status (only pending/confirmed can be cancelled).
    2. Compute refund percentage from days-until-check-in:
       - more than 7 days  → 100% refund
       - 2 to 7 days       → 50% refund
       - less than 2 days  → 0% (no refund)
    3. Mark the booking as cancelled (single DB commit).
    4. If percentage > 0 and the booking has a payment_id, call
       payment_service /refund. A failure there does NOT roll back the
       cancellation — the refund is recorded as failed and can be retried.
    5. Publish booking.cancelled to SNS so inventory_service releases the
       room and notification_service alerts the traveler with the amount.
    """
    # Fetch booking
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Verify ownership
    if booking.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="You don't have permission to cancel this booking"
        )

    # Verify status - can only cancel pending or confirmed bookings
    if booking.status == "cancelled":
        raise HTTPException(status_code=400, detail="Booking is already cancelled")

    if booking.status not in ["pending", "confirmed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel booking with status: {booking.status}",
        )

    previous_status = booking.status

    # Calculate the refund based on the cancellation policy
    today = datetime.now(timezone.utc).date()
    refund_pct = calculate_refund_percentage(booking.check_in, today)
    days_left = days_until_check_in(booking.check_in, today)
    refund_amount = round(float(booking.total_price) * refund_pct, 2)

    # Mark booking as cancelled
    booking.status = "cancelled"
    await db.commit()
    await db.refresh(booking)

    # Trigger refund on payment_service if applicable
    refund_status = "no_refund"
    if refund_amount > 0 and booking.payment_id is not None:
        try:
            await request_refund(
                payment_id=booking.payment_id,
                amount=refund_amount,
                reason="user_cancelled",
            )
            refund_status = "processed"
        except PaymentServiceError:
            # Booking is already cancelled at this point; surface a flagged
            # state to downstream consumers so the user can be told and ops
            # can retry. We avoid logging payment details on purpose.
            refund_status = "failed"

    # Publish booking.cancelled — inventory + notification consumers handle the rest.
    # The publisher swallows AWS errors internally; cancellation must not depend
    # on it succeeding (it's a best-effort fanout).
    await sns_publisher.publish_booking_cancelled(
        booking_id=str(booking.id),
        user_id=str(booking.user_id),
        room_id=str(booking.room_id),
        hotel_id=str(booking.hotel_id),
        check_in=booking.check_in.isoformat(),
        check_out=booking.check_out.isoformat(),
        currency=booking.currency,
        refund_amount=str(refund_amount),
        refund_percentage=refund_pct,
        refund_status=refund_status,
        previous_status=previous_status,
    )

    # Build response
    from ..services.booking_service import build_booking_response

    response = build_booking_response(booking)
    await enrich_booking_responses([response], [booking])

    # Decorate with refund info — the response_model is intentionally absent on
    # this endpoint so we can return a richer dict than BookingResponse.
    response_dict = response.model_dump(by_alias=True)
    response_dict["cancellation"] = {
        "refundAmount": refund_amount,
        "refundPercentage": refund_pct,
        "refundStatus": refund_status,
        "daysUntilCheckIn": days_left,
    }
    return response_dict
