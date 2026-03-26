from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.accommodation_service import AccommodationService
from app.models.accommodation import Accommodation as AccommodationModel
import sys
sys.path.append('../../..')
from shared.schemas.accommodation import (
    AccommodationResponse,
    AccommodationUpdate,
    PopularityUpdate
)

router = APIRouter(prefix="/accommodations", tags=["accommodations"])


def accommodation_to_response(accommodation: AccommodationModel) -> dict:
    return {
        "id": str(accommodation.id),
        "external_id": accommodation.external_id,
        "provider": accommodation.provider,
        "title": accommodation.title,
        "description": accommodation.description,
        "accommodation_type": accommodation.accommodation_type.value,
        "location": accommodation.location,
        "pricing": accommodation.pricing,
        "capacity": accommodation.capacity,
        "rating": accommodation.rating,
        "popularity": accommodation.popularity,
        "amenities": accommodation.amenities,
        "images": accommodation.images,
        "availability": accommodation.availability,
        "policies": accommodation.policies,
        "status": accommodation.status.value,
        "created_at": accommodation.created_at,
        "updated_at": accommodation.updated_at,
    }


@router.get("", response_model=List[dict])
async def list_accommodations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    provider: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    accommodations = await AccommodationService.list_accommodations(
        db, skip=skip, limit=limit, provider=provider, status=status
    )
    return [accommodation_to_response(acc) for acc in accommodations]


@router.get("/{accommodation_id}", response_model=dict)
async def get_accommodation(
    accommodation_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    accommodation = await AccommodationService.get_accommodation(db, accommodation_id)
    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accommodation not found"
        )
    return accommodation_to_response(accommodation)


@router.put("/{accommodation_id}", response_model=dict)
async def update_accommodation(
    accommodation_id: UUID,
    accommodation_update: AccommodationUpdate,
    db: AsyncSession = Depends(get_db)
):
    update_data = accommodation_update.model_dump(exclude_unset=True)
    
    if 'location' in update_data and update_data['location']:
        update_data['location'] = update_data['location'].model_dump()
    if 'pricing' in update_data and update_data['pricing']:
        update_data['pricing'] = update_data['pricing'].model_dump()
    if 'capacity' in update_data and update_data['capacity']:
        update_data['capacity'] = update_data['capacity'].model_dump()
    if 'rating' in update_data and update_data['rating']:
        update_data['rating'] = update_data['rating'].model_dump()
    if 'popularity' in update_data and update_data['popularity']:
        update_data['popularity'] = update_data['popularity'].model_dump()
    if 'images' in update_data and update_data['images']:
        update_data['images'] = [img.model_dump() for img in update_data['images']]
    if 'availability' in update_data and update_data['availability']:
        update_data['availability'] = update_data['availability'].model_dump()
    if 'policies' in update_data and update_data['policies']:
        update_data['policies'] = update_data['policies'].model_dump()
    
    accommodation = await AccommodationService.update_accommodation(
        db, accommodation_id, update_data
    )
    
    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accommodation not found"
        )
    
    return accommodation_to_response(accommodation)


@router.patch("/{accommodation_id}/popularity", response_model=dict)
async def update_popularity(
    accommodation_id: UUID,
    popularity: PopularityUpdate,
    db: AsyncSession = Depends(get_db)
):
    accommodation = await AccommodationService.update_popularity(
        db,
        accommodation_id,
        views=popularity.views,
        bookings=popularity.bookings,
        favorites=popularity.favorites
    )
    
    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accommodation not found"
        )
    
    return accommodation_to_response(accommodation)


@router.delete("/{accommodation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_accommodation(
    accommodation_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    deleted = await AccommodationService.delete_accommodation(db, accommodation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Accommodation not found"
        )
    return None
