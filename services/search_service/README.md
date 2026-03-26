# Search Service

Search microservice - Provides fast accommodation search with Redis and RediSearch, consuming events from SQS.

## Features

- ✅ Redis with RediSearch for fast full-text search
- ✅ SQS consumer worker for async indexing
- ✅ Multiple filter support (price, type, rating, amenities, etc.)
- ✅ Sorting by price, rating, and popularity
- ✅ Pagination
- ✅ Search suggestions/autocomplete
- ✅ Sub-millisecond search performance

## Endpoints

### Search
- `GET /search` - Search accommodations with filters and sorting
  - Query params: city, min_price, max_price, accommodation_type, min_rating, min_guests, amenities, sort_by, sort_order, page, page_size
- `GET /search/suggestions` - Get search suggestions for autocomplete
- `DELETE /search/filters` - Clear all filters

### Accommodations
- `GET /accommodations/{id}` - Get accommodation from Redis cache

### System
- `GET /health` - Health check endpoint (includes Redis status)
- `GET /` - Service information

## Development

```bash
# Install dependencies
poetry install

# Run API service
poetry run uvicorn app.main:app --reload --port 8003

# Run SQS worker (in separate terminal)
poetry run python workers/sqs_worker.py

# Run tests
poetry run pytest
```

## Environment Variables

```bash
REDIS_URL=redis://localhost:6379
AWS_ENDPOINT_URL=http://localhost:4566  # LocalStack for local dev
SQS_QUEUE_URL=http://localhost:4566/000000000000/accommodation-sync-queue
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
SQS_POLL_INTERVAL=20
SQS_MAX_MESSAGES=10
```

## Docker

```bash
# Run API service
docker-compose up search-service

# Run worker
docker-compose up search-worker
```

## Search Examples

```bash
# Search by city
curl "http://localhost:8003/search?city=Madrid"

# Filter by price range
curl "http://localhost:8003/search?min_price=50&max_price=200"

# Multiple filters
curl "http://localhost:8003/search?city=Barcelona&accommodation_type=apartment&min_rating=4.5&sort_by=price&sort_order=asc"

# Search with amenities
curl "http://localhost:8003/search?amenities=wifi&amenities=pool"
```
