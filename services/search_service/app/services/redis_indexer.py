import json
from typing import Dict, Any
from app.redis_client import redis_client


class RedisIndexer:
    def __init__(self):
        self.client = redis_client.get_client()

    def index_accommodation(self, accommodation_id: str, accommodation_data: Dict[str, Any]) -> bool:
        try:
            key = f"accommodation:{accommodation_id}"
            
            self.client.json().set(key, "$", accommodation_data)
            
            print(f"✅ Indexed accommodation: {accommodation_id} - {accommodation_data.get('title')}")
            return True
        except Exception as e:
            print(f"❌ Error indexing accommodation {accommodation_id}: {e}")
            return False

    def update_accommodation(self, accommodation_id: str, accommodation_data: Dict[str, Any]) -> bool:
        return self.index_accommodation(accommodation_id, accommodation_data)

    def delete_accommodation(self, accommodation_id: str) -> bool:
        try:
            key = f"accommodation:{accommodation_id}"
            self.client.delete(key)
            print(f"✅ Deleted accommodation from index: {accommodation_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting accommodation {accommodation_id}: {e}")
            return False

    def get_accommodation(self, accommodation_id: str) -> Dict[str, Any] | None:
        try:
            key = f"accommodation:{accommodation_id}"
            data = self.client.json().get(key)
            return data
        except Exception as e:
            print(f"❌ Error getting accommodation {accommodation_id}: {e}")
            return None


indexer = RedisIndexer()
