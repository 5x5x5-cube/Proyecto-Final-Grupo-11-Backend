from fastapi import APIRouter, HTTPException, status
from app.services.redis_indexer import indexer

router = APIRouter(prefix="/accommodations", tags=["accommodations"])


@router.get("/{accommodation_id}")
async def get_accommodation(accommodation_id: str):
    """
    Get accommodation details by ID from Redis cache.
    
    This endpoint retrieves accommodation data from the search index,
    which is faster than querying the inventory service database.
    """
    accommodation = indexer.get_accommodation(accommodation_id)
    
    if not accommodation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Accommodation {accommodation_id} not found in search index"
        )
    
    return accommodation
