from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Hotel
from ..schemas.hotel import HotelCreate, HotelResponse
from ..services.sns_publisher import sns_publisher

router = APIRouter(prefix="/hotels", tags=["hotels"])


@router.post("/webhook", response_model=HotelResponse, status_code=201)
async def register_hotel_webhook(hotel_data: HotelCreate, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint to register a new hotel from external sources.
    Publishes event to SNS for synchronization with search service.
    """
    existing = await db.execute(select(Hotel).where(Hotel.name == hotel_data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Hotel already exists")

    new_hotel = Hotel(
        name=hotel_data.name,
        description=hotel_data.description,
        city=hotel_data.city,
        country=hotel_data.country,
        address=hotel_data.address,
        rating=hotel_data.rating,
    )

    db.add(new_hotel)
    await db.commit()
    await db.refresh(new_hotel)

    hotel_dict = {
        "id": str(new_hotel.id),
        "name": new_hotel.name,
        "description": new_hotel.description,
        "city": new_hotel.city,
        "country": new_hotel.country,
        "address": new_hotel.address,
        "rating": new_hotel.rating,
    }

    await sns_publisher.publish_hotel_created(hotel_dict)

    return new_hotel


@router.get("", response_model=List[HotelResponse])
async def list_hotels(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """List all hotels"""
    result = await db.execute(select(Hotel).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get hotel by ID"""
    result = await db.execute(select(Hotel).where(Hotel.id == hotel_id))
    hotel = result.scalar_one_or_none()
    if not hotel:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel
