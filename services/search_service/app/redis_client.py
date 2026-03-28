import redis
from redis.commands.search.field import NumericField, TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from app.config import get_settings

settings = get_settings()


class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.hotel_index = settings.redis_hotel_index
        self.room_index = settings.redis_room_index
        self.availability_index = settings.redis_availability_index

        self._ensure_indexes()

    def _ensure_indexes(self):
        self._ensure_hotel_index()
        self._ensure_room_index()
        self._ensure_availability_index()

    def _ensure_hotel_index(self):
        try:
            self.client.ft(self.hotel_index).info()
            print(f"Redis index '{self.hotel_index}' already exists")
        except redis.ResponseError:
            print(f"Creating Redis index '{self.hotel_index}'...")
            self._create_hotel_index()

    def _create_hotel_index(self):
        schema = (
            TextField("$.name", as_name="name", weight=2.0),
            TextField("$.description", as_name="description"),
            TextField("$.city", as_name="city"),
            TagField("$.country", as_name="country"),
            TextField("$.address", as_name="address"),
            NumericField("$.rating", as_name="rating", sortable=True),
        )
        definition = IndexDefinition(prefix=["hotel:"], index_type=IndexType.JSON)
        self.client.ft(self.hotel_index).create_index(schema, definition=definition)
        print(f"Redis index '{self.hotel_index}' created successfully")

    def _ensure_room_index(self):
        try:
            self.client.ft(self.room_index).info()
            print(f"Redis index '{self.room_index}' already exists")
        except redis.ResponseError:
            print(f"Creating Redis index '{self.room_index}'...")
            self._create_room_index()

    def _create_room_index(self):
        schema = (
            TagField("$.hotel_id", as_name="hotel_id"),
            TextField("$.room_type", as_name="room_type"),
            TextField("$.room_number", as_name="room_number"),
            NumericField("$.capacity", as_name="capacity", sortable=True),
            NumericField("$.price_per_night", as_name="price", sortable=True),
            NumericField("$.tax_rate", as_name="tax_rate"),
            NumericField("$.total_quantity", as_name="total_quantity"),
        )
        definition = IndexDefinition(prefix=["room:"], index_type=IndexType.JSON)
        self.client.ft(self.room_index).create_index(schema, definition=definition)
        print(f"Redis index '{self.room_index}' created successfully")

    def _ensure_availability_index(self):
        try:
            self.client.ft(self.availability_index).info()
            print(f"Redis index '{self.availability_index}' already exists")
        except redis.ResponseError:
            print(f"Creating Redis index '{self.availability_index}'...")
            self._create_availability_index()

    def _create_availability_index(self):
        schema = (
            TagField("$.room_id", as_name="room_id"),
            TextField("$.date", as_name="date"),
            NumericField("$.available_quantity", as_name="available_quantity", sortable=True),
        )
        definition = IndexDefinition(prefix=["availability:"], index_type=IndexType.JSON)
        self.client.ft(self.availability_index).create_index(schema, definition=definition)
        print(f"Redis index '{self.availability_index}' created successfully")

    def get_client(self):
        return self.client


redis_client = RedisClient()
