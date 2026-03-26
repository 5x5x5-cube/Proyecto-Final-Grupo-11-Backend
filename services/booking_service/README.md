# Booking Service

Manages confirmed reservation records. Receives pre-calculated booking data and persists it as a confirmed booking. Does not create holds or interact with the Inventory Service directly.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

## Endpoints

Endpoints that require user identification use the `X-User-Id` header (UUID).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/bookings` | Create a confirmed booking (requires `X-User-Id`) |
| GET | `/api/v1/bookings/{id}` | Booking detail |
| GET | `/api/v1/bookings` | List user's bookings (requires `X-User-Id`) |
| GET | `/health` | Health check |

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8002
poetry run pytest
poetry run black app/ tests/ --line-length 100
poetry run isort app/ tests/ --profile black --line-length 100
```
