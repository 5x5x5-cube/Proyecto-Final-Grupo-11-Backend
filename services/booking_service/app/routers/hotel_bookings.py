import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import BookingNotFoundError
from ..schemas import BookingResponse, HotelBookingListResponse, UpdateBookingStatusRequest
from ..services.booking_service import get_hotel_booking, list_hotel_bookings, update_booking_status

router = APIRouter(prefix="/api/v1/bookings/hotel", tags=["hotel-bookings"])


def get_hotel_id(request: Request) -> uuid.UUID:
    """Extract and validate the X-Hotel-Id header; return 401 if missing or invalid."""
    raw = request.headers.get("X-Hotel-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="X-Hotel-Id header is required")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-Hotel-Id header is not a valid UUID")


@router.get("", response_model=HotelBookingListResponse)
async def list_bookings(
    hotel_id: uuid.UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None, pattern="^(confirmed|pending|cancelled)$"),
    check_in_from: date | None = Query(None, alias="checkInFrom"),
    check_in_to: date | None = Query(None, alias="checkInTo"),
    code: str | None = Query(None, max_length=20),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
):
    return await list_hotel_bookings(
        db,
        hotel_id=hotel_id,
        status=status,
        check_in_from=check_in_from,
        check_in_to=check_in_to,
        code=code,
        page=page,
        limit=limit,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(
    booking_id: uuid.UUID,
    hotel_id: uuid.UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await get_hotel_booking(db, hotel_id=hotel_id, booking_id=booking_id)
    except BookingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{booking_id}/status", response_model=BookingResponse)
async def update_status(
    booking_id: uuid.UUID,
    request: UpdateBookingStatusRequest,
    hotel_id: uuid.UUID = Depends(get_hotel_id),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await update_booking_status(db, booking_id, hotel_id, request)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
