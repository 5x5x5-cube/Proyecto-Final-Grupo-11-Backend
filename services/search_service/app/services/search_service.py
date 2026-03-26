from typing import List, Dict, Any, Optional
from redis.commands.search.query import Query
from app.redis_client import redis_client
from app.config import get_settings

settings = get_settings()


class SearchService:
    def __init__(self):
        self.client = redis_client.get_client()
        self.index_name = settings.redis_index_name

    def build_query(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        accommodation_types: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        min_guests: Optional[int] = None,
        amenities: Optional[List[str]] = None,
    ) -> str:
        query_parts = []
        
        if city:
            query_parts.append(f"@city:{city}")
        
        if min_price is not None or max_price is not None:
            min_p = min_price if min_price is not None else 0
            max_p = max_price if max_price is not None else "+inf"
            query_parts.append(f"@price:[{min_p} {max_p}]")
        
        if accommodation_types:
            types_query = "|".join(accommodation_types)
            query_parts.append(f"@type:{{{types_query}}}")
        
        if min_rating is not None:
            query_parts.append(f"@rating:[{min_rating} 5.0]")
        
        if min_guests is not None:
            query_parts.append(f"@guests:[{min_guests} +inf]")
        
        if amenities:
            amenities_parts = [f"@amenities:{{{amenity}}}" for amenity in amenities]
            query_parts.append(f"({' '.join(amenities_parts)})")
        
        query_parts.append("@status:{active}")
        query_parts.append("@available:{true}")
        
        return " ".join(query_parts) if query_parts else "*"

    def search(
        self,
        city: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        accommodation_types: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        min_guests: Optional[int] = None,
        amenities: Optional[List[str]] = None,
        sort_by: str = "popularity",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        query_string = self.build_query(
            city=city,
            min_price=min_price,
            max_price=max_price,
            accommodation_types=accommodation_types,
            min_rating=min_rating,
            min_guests=min_guests,
            amenities=amenities,
        )

        sort_fields = {
            "price": "price",
            "rating": "rating",
            "popularity": "popularity"
        }
        sort_field = sort_fields.get(sort_by, "popularity")
        is_ascending = sort_order.lower() == "asc"

        offset = (page - 1) * page_size
        
        query = (
            Query(query_string)
            .sort_by(sort_field, asc=is_ascending)
            .paging(offset, page_size)
            .return_fields("$")
        )

        try:
            result = self.client.ft(self.index_name).search(query)
            
            accommodations = []
            for doc in result.docs:
                import json
                accommodation = json.loads(doc.json)
                accommodations.append(accommodation)

            total = result.total
            total_pages = (total + page_size - 1) // page_size

            return {
                "results": accommodations,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "filters_applied": {
                    "city": city,
                    "min_price": min_price,
                    "max_price": max_price,
                    "types": accommodation_types,
                    "min_rating": min_rating,
                    "min_guests": min_guests,
                    "amenities": amenities,
                },
                "sort": {
                    "by": sort_by,
                    "order": sort_order
                }
            }

        except Exception as e:
            print(f"❌ Search error: {e}")
            return {
                "results": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "filters_applied": {},
                "sort": {"by": sort_by, "order": sort_order},
                "error": str(e)
            }

    def get_suggestions(self, query: str, limit: int = 10) -> Dict[str, Any]:
        try:
            search_query = Query(f"@title:{query}* | @city:{query}*").paging(0, limit)
            result = self.client.ft(self.index_name).search(search_query)
            
            cities = set()
            accommodations = []
            
            for doc in result.docs:
                import json
                accommodation = json.loads(doc.json)
                cities.add(accommodation.get('location', {}).get('city', ''))
                accommodations.append({
                    "id": accommodation.get('id'),
                    "title": accommodation.get('title'),
                    "city": accommodation.get('location', {}).get('city'),
                    "price": accommodation.get('pricing', {}).get('total_price'),
                })

            return {
                "cities": list(cities),
                "accommodations": accommodations[:limit]
            }

        except Exception as e:
            print(f"❌ Suggestions error: {e}")
            return {"cities": [], "accommodations": []}


search_service = SearchService()
