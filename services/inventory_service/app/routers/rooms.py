import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Availability, Hotel, Room
from ..schemas import AvailabilityRangeResponse, AvailabilityResponse, HotelResponse, RoomResponse
from ..services.availability_service import check_availability, get_room
from ..services.sqs_publisher import sqs_publisher

router = APIRouter(prefix="/rooms", tags=["rooms"])


class RoomCreate(BaseModel):
    hotel_id: uuid.UUID
    room_type: str = Field(..., min_length=1, max_length=50)
    room_number: str | None = Field(None, max_length=20)
    capacity: int = Field(..., ge=1)
    price_per_night: float = Field(..., gt=0)
    tax_rate: float = Field(default=0.19, ge=0, le=1)
    description: str | None = None
    amenities: dict | None = None
    total_quantity: int = Field(default=1, ge=1)
    availability_days: int = Field(default=60, ge=1, le=365)


@router.post("", response_model=RoomResponse, status_code=201)
async def create_room(room_data: RoomCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new room with automatic availability generation.
    Publishes events to SQS for synchronization with search service.
    """
    # Verify hotel exists
    hotel_result = await db.execute(select(Hotel).where(Hotel.id == room_data.hotel_id))
    hotel = hotel_result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail=f"Hotel {room_data.hotel_id} not found")

    # Create room
    new_room = Room(
        hotel_id=room_data.hotel_id,
        room_type=room_data.room_type,
        room_number=room_data.room_number,
        capacity=room_data.capacity,
        price_per_night=room_data.price_per_night,
        tax_rate=room_data.tax_rate,
        description=room_data.description,
        amenities=room_data.amenities,
        total_quantity=room_data.total_quantity,
    )

    db.add(new_room)
    await db.flush()

    # Publish room created event to SQS
    room_dict = {
        "id": str(new_room.id),
        "hotel_id": str(new_room.hotel_id),
        "room_type": new_room.room_type,
        "room_number": new_room.room_number,
        "capacity": new_room.capacity,
        "price_per_night": float(new_room.price_per_night),
        "tax_rate": float(new_room.tax_rate),
        "total_quantity": new_room.total_quantity,
        "amenities": new_room.amenities,
    }
    await sqs_publisher.publish_room_created(room_dict)

    # Generate availability for the next N days
    today = date.today()
    for i in range(room_data.availability_days):
        avail_date = today + timedelta(days=i)
        availability = Availability(
            room_id=new_room.id,
            date=avail_date,
            total_quantity=room_data.total_quantity,
            available_quantity=room_data.total_quantity,
        )
        db.add(availability)

        # Publish availability created event to SQS
        await sqs_publisher.publish_availability_created(
            {
                "room_id": str(new_room.id),
                "date": str(avail_date),
                "available_quantity": room_data.total_quantity,
            }
        )

    await db.commit()
    await db.refresh(new_room)

    return new_room


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
