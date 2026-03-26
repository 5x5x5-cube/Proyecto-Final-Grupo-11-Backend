from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.accommodation_service import AccommodationService
import sys
sys.path.append('../../..')
from shared.schemas.accommodation import AccommodationCreate, AccommodationResponse

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/accommodation", status_code=status.HTTP_202_ACCEPTED)
async def receive_accommodation_webhook(
    accommodation: AccommodationCreate,
    db: AsyncSession = Depends(get_db)
):
    existing = await AccommodationService.get_accommodation_by_external_id(
        db,
        accommodation.external_id,
        accommodation.provider
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Accommodation with external_id {accommodation.external_id} from {accommodation.provider} already exists"
        )
    
    accommodation_data = {
        "external_id": accommodation.external_id,
        "provider": accommodation.provider,
        "title": accommodation.title,
        "description": accommodation.description,
        "accommodation_type": accommodation.accommodation_type,
        "location": accommodation.location.model_dump(),
        "pricing": accommodation.pricing.model_dump(),
        "capacity": accommodation.capacity.model_dump(),
        "rating": accommodation.rating.model_dump(),
        "popularity": accommodation.popularity.model_dump(),
        "amenities": accommodation.amenities,
        "images": [img.model_dump() for img in accommodation.images],
        "availability": accommodation.availability.model_dump(),
        "policies": accommodation.policies.model_dump(),
    }
    
    db_accommodation = await AccommodationService.create_accommodation(db, accommodation_data)
    
    return {
        "message": "Accommodation received and queued for processing",
        "accommodation_id": str(db_accommodation.id),
        "external_id": db_accommodation.external_id
    }
