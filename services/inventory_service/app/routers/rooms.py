import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Hotel, Room
from ..schemas import AvailabilityRangeResponse, AvailabilityResponse, HotelResponse, RoomResponse
from ..services.availability_service import check_availability, get_room

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room_detail(room_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    room = await get_room(db, room_id)
    return room


@router.get("/{room_id}/hotel", response_model=HotelResponse)
async def get_room_hotel(room_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    room = await get_room(db, room_id)
    result = await db.execute(select(Hotel).where(Hotel.id == room.hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.get("/{room_id}/availability", response_model=AvailabilityRangeResponse)
async def get_availability(
    room_id: uuid.UUID,
    check_in: date = Query(..., alias="checkIn"),
    check_out: date = Query(..., alias="checkOut"),
    db: AsyncSession = Depends(get_db),
):
    rows = await check_availability(db, room_id, check_in, check_out)
    return AvailabilityRangeResponse(
        room_id=room_id,
        check_in=check_in,
        check_out=check_out,
        is_available=all(r.available_quantity > 0 for r in rows),
        dates=[AvailabilityResponse.model_validate(r) for r in rows],
    )
