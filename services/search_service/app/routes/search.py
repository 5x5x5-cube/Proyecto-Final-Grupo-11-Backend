from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.search_service import search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/destinations")
async def get_destinations():
    """
    Retorna la lista de destinos disponibles para el selector de búsqueda.
    Los destinos se obtienen dinámicamente de los hoteles indexados en Redis,
    garantizando que solo se muestren ciudades con hospedajes activos.
    """
    destinos = search_service.get_destinations()
    return {
        "destinations": destinos,
        "total": len(destinos),
    }


@router.get("/hotels")
async def search_hotels(
    city: Optional[str] = Query(None, description="City to search in"),
    check_in: Optional[date] = Query(None, description="Check-in date (YYYY-MM-DD)"),
    check_out: Optional[date] = Query(None, description="Check-out date (YYYY-MM-DD)"),
    guests: Optional[int] = Query(None, ge=1, description="Number of guests"),
    min_rating: Optional[float] = Query(None, ge=0, le=5, description="Minimum rating"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    Search hotels by city, dates, and number of guests.

    **Validations:**
    - Check-out date must be after check-in date
    - Check-in date cannot be in the past
    - Number of guests must be greater than zero

    **Returns:**
    - List of hotels with available rooms
    - Hotel information: name, location, rating, price per night, services
    - Button to view rooms available
    """

    if check_in and check_out:
        if check_out <= check_in:
            raise HTTPException(
                status_code=400, detail="Check-out date must be after check-in date"
            )

    if check_in:
        if check_in < date.today():
            raise HTTPException(status_code=400, detail="Check-in date cannot be in the past")

    if guests is not None and guests <= 0:
        raise HTTPException(status_code=400, detail="Number of guests must be greater than zero")

    result = search_service.search_hotels(
        city=city,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        min_rating=min_rating,
        page=page,
        page_size=page_size,
    )

    if result["total"] == 0:
        return {
            **result,
            "message": "No hotels available matching your search criteria",
        }

    return result


@router.get("/hotels/{hotel_id}")
async def get_hotel_detail(hotel_id: str):
    """
    Retorna el detalle completo de un hotel por su ID.
    Se usa en la pantalla de detalle de propiedad del móvil (HU2.2M).
    El hotel se busca directamente por key en Redis (hotel:{hotel_id}).
    """
    hotel = search_service.get_hotel_by_id(hotel_id)
    if hotel is None:
        raise HTTPException(status_code=404, detail=f"Hotel '{hotel_id}' no encontrado")
    return hotel


@router.get("/hotels/{hotel_id}/rooms")
async def get_hotel_rooms(hotel_id: str):
    """
    Retorna las habitaciones disponibles de un hotel específico.
    Se usa cuando el usuario presiona 'Ver habitaciones' en la pantalla de detalle.
    """
    rooms = search_service.get_hotel_rooms(hotel_id)

    if not rooms:
        return {"hotel_id": hotel_id, "rooms": [], "message": "No rooms available"}

    return {"hotel_id": hotel_id, "rooms": rooms, "total": len(rooms)}
