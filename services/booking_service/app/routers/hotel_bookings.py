import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas import BookingResponse, UpdateBookingStatusRequest
from ..services.booking_service import update_booking_status

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


@router.get("")
async def list_hotel_bookings():
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/{booking_id}")
async def get_hotel_booking(booking_id: uuid.UUID):
    raise HTTPException(status_code=501, detail="Not implemented yet")


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
