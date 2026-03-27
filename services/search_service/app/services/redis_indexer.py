from typing import Any, Dict, Optional

from app.redis_client import redis_client


class RedisIndexer:
    def __init__(self):
        self.client = redis_client.get_client()

    def index_hotel(self, hotel_id: str, hotel_data: Dict[str, Any]) -> bool:
        try:
            key = f"hotel:{hotel_id}"
            self.client.json().set(key, "$", hotel_data)
            print(f"Indexed hotel: {hotel_id} - {hotel_data.get('name')}")
            return True
        except Exception as e:
            print(f"Error indexing hotel {hotel_id}: {e}")
            return False

    def update_hotel(self, hotel_id: str, hotel_data: Dict[str, Any]) -> bool:
        return self.index_hotel(hotel_id, hotel_data)

    def delete_hotel(self, hotel_id: str) -> bool:
        try:
            key = f"hotel:{hotel_id}"
            self.client.delete(key)
            print(f"Deleted hotel from index: {hotel_id}")
            return True
        except Exception as e:
            print(f"Error deleting hotel {hotel_id}: {e}")
            return False

    def index_room(self, room_id: str, room_data: Dict[str, Any]) -> bool:
        try:
            key = f"room:{room_id}"
            self.client.json().set(key, "$", room_data)
            print(f"Indexed room: {room_id} - {room_data.get('room_number')}")
            return True
        except Exception as e:
            print(f"Error indexing room {room_id}: {e}")
            return False

    def update_room(self, room_id: str, room_data: Dict[str, Any]) -> bool:
        return self.index_room(room_id, room_data)

    def delete_room(self, room_id: str) -> bool:
        try:
            key = f"room:{room_id}"
            self.client.delete(key)
            print(f"Deleted room from index: {room_id}")
            return True
        except Exception as e:
            print(f"Error deleting room {room_id}: {e}")
            return False


indexer = RedisIndexer()
