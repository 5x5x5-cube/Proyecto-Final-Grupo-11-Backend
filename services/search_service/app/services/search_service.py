import json
from datetime import date
from typing import Any, Dict, List, Optional

from redis.commands.search.query import Query

from app.config import get_settings
from app.redis_client import redis_client
from app.services.redis_indexer import indexer

settings = get_settings()


class SearchService:
    def __init__(self):
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
        query_parts = []

        if city:
            query_parts.append(f"@city:{city}")

        if min_rating is not None:
            query_parts.append(f"@rating:[{min_rating} 5.0]")

        query_string = " ".join(query_parts) if query_parts else "*"
        offset = (page - 1) * page_size
        query = Query(query_string).paging(offset, page_size).return_fields("$")

        try:
            result = self.client.ft(self.hotel_index).search(query)

            hotels = []
            for doc in result.docs:
                hotel_data = json.loads(doc.json)
                hotel_id = hotel_data.get("id")

                rooms = self._get_available_rooms(hotel_id, guests, check_in, check_out)

                if rooms or (not guests and not check_in and not check_out):
                    hotel_data["available_rooms_count"] = len(rooms)
                    hotel_data["min_price"] = (
                        min(r["price_per_night"] for r in rooms) if rooms else None
                    )
                    hotels.append(hotel_data)

            total = len(hotels)
            total_pages = (total + page_size - 1) // page_size

            return {
                "results": hotels,
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

    def _get_available_rooms(
        self,
        hotel_id: str,
        min_capacity: Optional[int] = None,
        check_in: Optional[date] = None,
        check_out: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        escaped_hotel_id = hotel_id.replace("-", "\\-")
        query_parts = [f"@hotel_id:{{{escaped_hotel_id}}}"]

        if min_capacity:
            query_parts.append(f"@capacity:[{min_capacity} +inf]")

        query_string = " ".join(query_parts)
        query = Query(query_string).return_fields("$")

        try:
            result = self.client.ft(self.room_index).search(query)
            rooms = []
            for doc in result.docs:
                room_data = json.loads(doc.json)
                room_id = room_data.get("id")

                if check_in and check_out:
                    if not indexer.is_room_available_for_dates(room_id, check_in, check_out):
                        continue

                rooms.append(room_data)
            return rooms
        except Exception as e:
            print(f"Error getting rooms: {e}")
            return []

    def get_hotel_rooms(self, hotel_id: str) -> List[Dict[str, Any]]:
        """Get all rooms for a specific hotel"""
        return self._get_available_rooms(hotel_id)


search_service = SearchService()