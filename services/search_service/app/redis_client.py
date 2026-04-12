import json as json_module

import redis

from app.config import get_settings

settings = get_settings()


class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.hotel_index = settings.redis_hotel_index
        self.room_index = settings.redis_room_index
        self.availability_index = settings.redis_availability_index
        self.search_available = False

        self._try_ensure_indexes()

    def _try_ensure_indexes(self):
        try:
            from redis.commands.search.field import NumericField, TagField, TextField
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType

            self._ensure_index(
                self.hotel_index,
                (
                    TextField("$.name", as_name="name", weight=2.0),
                    TextField("$.description", as_name="description"),
                    TextField("$.city", as_name="city"),
                    TagField("$.country", as_name="country"),
                    TextField("$.address", as_name="address"),
                    NumericField("$.rating", as_name="rating", sortable=True),
                ),
                IndexDefinition(prefix=["hotel:"], index_type=IndexType.JSON),
            )
            self._ensure_index(
                self.room_index,
                (
                    TagField("$.hotel_id", as_name="hotel_id"),
                    TextField("$.room_type", as_name="room_type"),
                    TextField("$.room_number", as_name="room_number"),
                    NumericField("$.capacity", as_name="capacity", sortable=True),
                    NumericField("$.price_per_night", as_name="price", sortable=True),
                    NumericField("$.tax_rate", as_name="tax_rate"),
                    NumericField("$.total_quantity", as_name="total_quantity"),
                ),
                IndexDefinition(prefix=["room:"], index_type=IndexType.JSON),
            )
            self._ensure_index(
                self.availability_index,
                (
                    TagField("$.room_id", as_name="room_id"),
                    TextField("$.date", as_name="date"),
                    NumericField(
                        "$.available_quantity", as_name="available_quantity", sortable=True
                    ),
                ),
                IndexDefinition(prefix=["availability:"], index_type=IndexType.JSON),
            )
            self.search_available = True
            print("RediSearch indexes ready")
        except Exception as e:
            self.search_available = False
            print(f"WARNING: RediSearch not available ({e}). Using fallback scan-based search.")

    def _ensure_index(self, index_name, schema, definition):
        try:
            self.client.ft(index_name).info()
            print(f"Redis index '{index_name}' already exists")
        except redis.ResponseError:
            print(f"Creating Redis index '{index_name}'...")
            self.client.ft(index_name).create_index(schema, definition=definition)
            print(f"Redis index '{index_name}' created successfully")

    def get_client(self):
        return self.client

    def json_set(self, key, data):
        if self.search_available:
            try:
                self.client.json().set(key, "$", data)
                return
            except Exception:  # nosec B110
                pass
        self.client.set(key, json_module.dumps(data))

    def json_get(self, key, path=None):
        if self.search_available:
            try:
                result = self.client.json().get(key, path or "$")
                if result and isinstance(result, list):
                    return result[0] if path and path != "$" else result
                return result
            except Exception:  # nosec B110
                pass
        raw = self.client.get(key)
        if raw is None:
            return None
        data = json_module.loads(raw)
        if path and path.startswith("$."):
            field = path[2:]
            return data.get(field)
        return [data] if isinstance(data, dict) else data

    def json_delete(self, key):
        self.client.delete(key)

    def scan_keys(self, pattern, count=500):
        keys = []
        cursor = 0
        while True:
            cursor, batch = self.client.scan(cursor=cursor, match=pattern, count=100)
            keys.extend(batch)
            if cursor == 0 or len(keys) >= count:
                break
        return keys[:count]


redis_client = RedisClient()
