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
    Cancel an active booking.

    Requirements:
    - Booking must belong to the authenticated user
    - Booking must be in 'confirmed' or 'pending' status
    - Cannot cancel an already cancelled booking

    Process (basic implementation):
    1. Validate booking ownership and status
    2. Update status to 'cancelled'
    3. Return success response

    Note: This is a basic implementation. Future enhancements will include:
    - Room release in inventory service
    - Refund processing in payment service
    - User notification via notification service
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

    # Update status to cancelled
    booking.status = "cancelled"
    await db.commit()
    await db.refresh(booking)

    # Build response
    from ..services.booking_service import build_booking_response

    response = build_booking_response(booking)
    await enrich_booking_responses([response], [booking])

    return response
