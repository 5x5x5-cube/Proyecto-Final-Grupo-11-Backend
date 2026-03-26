from typing import List, Optional
from fastapi import APIRouter, Query
from app.services.search_service import search_service
from app.services.redis_indexer import indexer

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def search_accommodations(
    city: Optional[str] = Query(None, description="Filter by city"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    accommodation_type: Optional[List[str]] = Query(None, description="Filter by accommodation type"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating (0-5)"),
    min_guests: Optional[int] = Query(None, ge=1, description="Minimum number of guests"),
    amenities: Optional[List[str]] = Query(None, description="Required amenities"),
    sort_by: str = Query("popularity", regex="^(price|rating|popularity)$", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """
    Search accommodations with multiple filters and sorting options.
    
    **Filters:**
    - city: Filter by city name
    - min_price, max_price: Price range filter
    - accommodation_type: Filter by type (hotel, hostel, apartment, house, villa, cabin)
    - min_rating: Minimum rating (0-5)
    - min_guests: Minimum guest capacity
    - amenities: Required amenities (can specify multiple)
    
    **Sorting:**
    - sort_by: Field to sort by (price, rating, popularity)
    - sort_order: Sort direction (asc, desc)
    
    **Pagination:**
    - page: Page number (starts at 1)
    - page_size: Number of results per page (max 100)
    """
    
    result = search_service.search(
        city=city,
        min_price=min_price,
        max_price=max_price,
        accommodation_types=accommodation_type,
        min_rating=min_rating,
        min_guests=min_guests,
        amenities=amenities,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
    
    return result


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of suggestions")
):
    """
    Get search suggestions for autocomplete.
    
    Returns matching cities and accommodation titles.
    """
    return search_service.get_suggestions(q, limit)


@router.delete("/filters")
async def clear_filters():
    """
    Clear all filters and return to default search.
    
    This is a convenience endpoint that returns the same result as
    calling /search without any parameters.
    """
    return {
        "message": "Filters cleared",
        "info": "Call GET /search without parameters to see all results"
    }
