# Inventory Service

Inventory management microservice - Receives accommodations from third-party providers via webhooks and publishes events to SQS for indexing.

## Features

- ✅ Webhook endpoint for receiving accommodations from third parties
- ✅ PostgreSQL storage with SQLAlchemy async
- ✅ AWS SQS event publishing
- ✅ Full CRUD operations for accommodations
- ✅ Popularity tracking (views, bookings, favorites)
- ✅ Database migrations with Alembic

## Endpoints

### Webhooks
- `POST /webhooks/accommodation` - Receive accommodation from third-party provider

### Accommodations
- `GET /accommodations` - List all accommodations (with filters)
- `GET /accommodations/{id}` - Get accommodation by ID
- `PUT /accommodations/{id}` - Update accommodation
- `PATCH /accommodations/{id}/popularity` - Update popularity metrics
- `DELETE /accommodations/{id}` - Delete accommodation

### System
- `GET /health` - Health check endpoint
- `GET /` - Service information

## Development

```bash
# Install dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Run service
poetry run uvicorn app.main:app --reload --port 8006

# Run tests
poetry run pytest

# Create new migration
poetry run alembic revision --autogenerate -m "description"
```

## Environment Variables

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db
AWS_ENDPOINT_URL=http://localhost:4566  # LocalStack for local dev
SQS_QUEUE_URL=http://localhost:4566/000000000000/accommodation-sync-queue
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
```

## Docker

```bash
docker-compose up inventory-service
```
