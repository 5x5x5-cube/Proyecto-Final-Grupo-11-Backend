"""Core booking business logic."""

import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import BookingAlreadyProcessedError, BookingNotFoundError
from ..models import Booking
from ..schemas import (
    BookingResponse,
    BookingTimelineEvent,
    CreateBookingRequest,
    HotelBookingListResponse,
    HotelBookingSummary,
    PriceBreakdown,
    UpdateBookingStatusRequest,
)

# Descripciones de eventos para el timeline según el estado de la reserva
_TIMELINE_DESCRIPTIONS: dict[str, str] = {
    "hold_created": "Habitación reservada temporalmente (hold de 15 min)",
    "booking_created": "Reserva registrada en el sistema",
    "confirmed": "Reserva confirmada por el hotel",
    "rejected": "Reserva rechazada por el hotel",
    "cancelled": "Reserva cancelada",
}


def _build_timeline(booking: Booking) -> list[BookingTimelineEvent]:
    """Deriva la línea de tiempo de la reserva a partir de sus datos persistidos."""
    events: list[BookingTimelineEvent] = []

    # Evento 1 — hold creado (si existe hold_id usamos created_at como referencia)
    if booking.hold_id:
        events.append(
            BookingTimelineEvent(
                event="hold_created",
                timestamp=booking.created_at,
                description=_TIMELINE_DESCRIPTIONS["hold_created"],
            )
        )

    # Evento 2 — reserva creada
    events.append(
        BookingTimelineEvent(
            event="booking_created",
            timestamp=booking.created_at,
            description=_TIMELINE_DESCRIPTIONS["booking_created"],
        )
    )

    # Evento 3 — estado final (si ya no está pendiente)
    if booking.status in ("confirmed", "rejected", "cancelled"):
        events.append(
            BookingTimelineEvent(
                event=booking.status,
                timestamp=booking.updated_at,
                description=_TIMELINE_DESCRIPTIONS[booking.status],
            )
        )

    return events


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
        guestName=booking.guest_name,
        guestEmail=booking.guest_email,
        guestPhone=booking.guest_phone,
        timeline=_build_timeline(booking),
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
        guest_name=request.guest_name,
        guest_email=request.guest_email,
        guest_phone=request.guest_phone,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return build_booking_response(booking)


async def list_hotel_bookings(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    status: str | None,
    check_in_from: date | None,
    check_in_to: date | None,
    code: str | None,
    page: int,
    limit: int,
) -> HotelBookingListResponse:
    """List bookings for a hotel with optional filters and pagination."""
    base_query = select(Booking).where(Booking.hotel_id == hotel_id)

    if status:
        base_query = base_query.where(Booking.status == status)
    if check_in_from:
        base_query = base_query.where(Booking.check_in >= check_in_from)
    if check_in_to:
        base_query = base_query.where(Booking.check_in <= check_in_to)
    if code:
        base_query = base_query.where(Booking.code.ilike(f"%{code}%"))

    # Conteo total para paginación
    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    # Conteo por estado para el resumen
    summary_query = (
        select(Booking.status, func.count())
        .where(Booking.hotel_id == hotel_id)
        .group_by(Booking.status)
    )
    summary_result = await db.execute(summary_query)
    counts: dict[str, int] = {row[0]: row[1] for row in summary_result.all()}
    summary = HotelBookingSummary(
        total=sum(counts.values()),
        confirmed=counts.get("confirmed", 0),
        pending=counts.get("pending", 0),
        cancelled=counts.get("cancelled", 0),
    )

    # Página de resultados
    offset = (page - 1) * limit
    paged_query = base_query.order_by(Booking.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(paged_query)
    bookings = result.scalars().all()

    return HotelBookingListResponse(
        data=[build_booking_response(b) for b in bookings],
        total=total,
        page=page,
        limit=limit,
        summary=summary,
    )


async def get_hotel_booking(
    db: AsyncSession,
    hotel_id: uuid.UUID,
    booking_id: uuid.UUID,
) -> BookingResponse:
    """Get a single booking scoped to a hotel."""
    result = await db.execute(
        select(Booking).where(Booking.id == booking_id, Booking.hotel_id == hotel_id)
    )
    booking = result.scalar_one_or_none()
    if not booking:
        raise BookingNotFoundError(str(booking_id))
    return build_booking_response(booking)


async def update_booking_status(
    db: AsyncSession,
    booking_id: uuid.UUID,
    hotel_id: uuid.UUID,
    request: UpdateBookingStatusRequest,
) -> BookingResponse:
    """Confirm or reject a pending booking for a given hotel."""
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise BookingNotFoundError(str(booking_id))
    if booking.hotel_id != hotel_id:
        raise PermissionError("Booking does not belong to this hotel")
    if booking.status != "pending":
        raise BookingAlreadyProcessedError(str(booking_id), booking.status)

    booking.status = "confirmed" if request.action == "confirm" else "rejected"

    await db.commit()
    await db.refresh(booking)
    return build_booking_response(booking)
