import json
from datetime import date
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.redis_client import redis_client
from app.services.redis_indexer import indexer

settings = get_settings()


class SearchService:
    def __init__(self):
        self.rc = redis_client
        self.client = redis_client.get_client()
        self.hotel_index = settings.redis_hotel_index
        self.room_index = settings.redis_room_index

    def search_hotels(
        self,
        city: Optional[str] = None,
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
        guests: Optional[int] = None,
        min_rating: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        try:
            if self.rc.search_available:
                hotels = self._search_hotels_ft(city, min_rating, page, page_size)
            else:
                hotels = self._search_hotels_scan(city, min_rating, page, page_size)

            filtered = []
            for hotel_data in hotels:
                hotel_id = hotel_data.get("id")
                rooms = self._get_available_rooms(hotel_id, guests, check_in, check_out)

                if rooms or (not guests and not check_in and not check_out):
                    hotel_data["available_rooms_count"] = len(rooms)
                    hotel_data["min_price"] = (
                        min(r["price_per_night"] for r in rooms) if rooms else None
                    )
                    amenities: dict = {}
                    for room in rooms:
                        for key, val in (room.get("amenities") or {}).items():
                            if val:
                                amenities[key] = True
                    hotel_data["amenities"] = amenities
                    filtered.append(hotel_data)

            total = len(filtered)
            total_pages = (total + page_size - 1) // page_size

            return {
                "results": filtered,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "filters": {
                    "city": city,
                    "check_in": str(check_in) if check_in else None,
                    "check_out": str(check_out) if check_out else None,
                    "guests": guests,
                    "min_rating": min_rating,
                },
            }
        except Exception as e:
            print(f"Search error: {e}")
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "filters": {},
                "error": str(e),
            }

    def _search_hotels_ft(self, city, min_rating, page, page_size):
        from redis.commands.search.query import Query

        query_parts = []
        if city:
            query_parts.append(f"@city:{city}")
        if min_rating is not None:
            query_parts.append(f"@rating:[{min_rating} 5.0]")
        query_string = " ".join(query_parts) if query_parts else "*"
        offset = (page - 1) * page_size
        query = Query(query_string).paging(offset, page_size).return_fields("$")
        result = self.client.ft(self.hotel_index).search(query)
        return [json.loads(doc.json) for doc in result.docs]

    def _search_hotels_scan(self, city, min_rating, page, page_size):
        keys = self.rc.scan_keys("hotel:*")
        hotels = []
        for key in keys:
            data = self.rc.json_get(key)
            if not data:
                continue
            hotel = data[0] if isinstance(data, list) else data
            if city and city.lower() not in hotel.get("city", "").lower():
                continue
            if min_rating is not None and (hotel.get("rating") or 0) < min_rating:
                continue
            hotels.append(hotel)
        offset = (page - 1) * page_size
        return hotels[offset : offset + page_size]

    def _get_available_rooms(
        self,
        hotel_id: str,
        min_capacity: Optional[int] = None,
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if self.rc.search_available:
                rooms_data = self._get_rooms_ft(hotel_id, min_capacity)
            else:
                rooms_data = self._get_rooms_scan(hotel_id, min_capacity)

            if not check_in or not check_out:
                return rooms_data

            return [
                r for r in rooms_data
                if indexer.is_room_available_for_dates(r.get("id"), check_in, check_out)
            ]
        except Exception as e:
            print(f"Error getting rooms: {e}")
            return []

    def _get_rooms_ft(self, hotel_id, min_capacity):
        from redis.commands.search.query import Query

        escaped_hotel_id = hotel_id.replace("-", "\\-")
        query_parts = [f"@hotel_id:{{{escaped_hotel_id}}}"]
        if min_capacity:
            query_parts.append(f"@capacity:[{min_capacity} +inf]")
        query_string = " ".join(query_parts)
        query = Query(query_string).return_fields("$")
        result = self.client.ft(self.room_index).search(query)
        return [json.loads(doc.json) for doc in result.docs]

    def _get_rooms_scan(self, hotel_id, min_capacity):
        keys = self.rc.scan_keys("room:*")
        rooms = []
        for key in keys:
            data = self.rc.json_get(key)
            if not data:
                continue
            room = data[0] if isinstance(data, list) else data
            if room.get("hotel_id") != hotel_id:
                continue
            if min_capacity and (room.get("capacity") or 0) < min_capacity:
                continue
            rooms.append(room)
        return rooms

    def get_hotel_rooms(self, hotel_id: str) -> List[Dict[str, Any]]:
        """Retorna todas las habitaciones de un hotel específico"""
        return self._get_available_rooms(hotel_id)

    def get_hotel_by_id(self, hotel_id: str) -> Optional[Dict[str, Any]]:
        """
        Retorna el detalle de un hotel buscándolo directamente por su key en Redis.
        Los hoteles se almacenan con key hotel:{id} vía el redis_indexer.
        Retorna None si el hotel no existe en el índice.
        """
        key = f"hotel:{hotel_id}"
        try:
            result = self.rc.json_get(key)
            if not result:
                return None
            return result[0] if isinstance(result, list) else result
        except Exception as e:
            print(f"Error obteniendo hotel {hotel_id}: {e}")
            return None

    def get_destinations(self) -> List[Dict[str, str]]:
        """
        Retorna la lista de destinos únicos disponibles para búsqueda.
        Los destinos se extraen de los hoteles indexados en Redis,
        eliminando duplicados y ordenando alfabéticamente por ciudad.
        """
        try:
            if self.rc.search_available:
                hotels = self._search_hotels_ft(None, None, 1, 500)
            else:
                hotels = self._search_hotels_scan(None, None, 1, 500)

            ciudades_vistas: set = set()
            destinos: List[Dict[str, str]] = []

            for hotel_data in hotels:
                ciudad = hotel_data.get("city", "").strip()
                pais = hotel_data.get("country", "").strip()
                if ciudad and ciudad not in ciudades_vistas:
                    ciudades_vistas.add(ciudad)
                    destinos.append({"city": ciudad, "country": pais})

            destinos.sort(key=lambda d: d["city"])
            return destinos
        except Exception as e:
            print(f"Error obteniendo destinos: {e}")
            return []


search_service = SearchService()
