import redis
from redis.commands.search.field import TextField, NumericField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from app.config import get_settings

settings = get_settings()


class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.index_name = settings.redis_index_name
        self._ensure_index()

    def _ensure_index(self):
        try:
            self.client.ft(self.index_name).info()
            print(f"✅ Redis index '{self.index_name}' already exists")
        except redis.ResponseError:
            print(f"📝 Creating Redis index '{self.index_name}'...")
            self._create_index()

    def _create_index(self):
        schema = (
            TextField("$.title", as_name="title", weight=2.0),
            TextField("$.description", as_name="description"),
            TagField("$.accommodation_type", as_name="type"),
            TextField("$.location.city", as_name="city"),
            TagField("$.location.country", as_name="country"),
            NumericField("$.pricing.total_price", as_name="price", sortable=True),
            NumericField("$.rating.average", as_name="rating", sortable=True),
            NumericField("$.popularity.popularity_score", as_name="popularity", sortable=True),
            NumericField("$.capacity.max_guests", as_name="guests"),
            TagField("$.amenities[*]", as_name="amenities"),
            TagField("$.status", as_name="status"),
            TagField("$.availability.is_available", as_name="available"),
        )

        definition = IndexDefinition(
            prefix=["accommodation:"],
            index_type=IndexType.JSON
        )

        self.client.ft(self.index_name).create_index(
            schema,
            definition=definition
        )
        print(f"✅ Redis index '{self.index_name}' created successfully")

    def get_client(self):
        return self.client


redis_client = RedisClient()
