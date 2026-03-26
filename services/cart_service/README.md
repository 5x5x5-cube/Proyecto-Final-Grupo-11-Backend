# Cart Service

Shopping cart microservice that manages the checkout cart lifecycle. Creates and manages 15-minute inventory holds via the Inventory Service when a user adds a room to their cart.

**Core concept**: Cart = Hold. When a user selects a room, the cart service creates an inventory hold that blocks availability for 15 minutes. One active cart per user.

## Endpoints

All cart endpoints require the `X-User-Id` header (UUID).

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| PUT | `/api/v1/cart` | Upsert cart + create hold | 200 / 409 |
| GET | `/api/v1/cart` | Get current cart | 200 / 404 / 410 |
| DELETE | `/api/v1/cart` | Delete cart + release hold | 204 / 404 |
| GET | `/health` | Health check | 200 |

### PUT /api/v1/cart

Creates or replaces the user's cart. If the user already has a cart with a different room, the old hold is released first. Idempotent for the same room+dates.

**Request:**
```json
{
  "roomId": "uuid",
  "hotelId": "uuid",
  "checkIn": "2026-04-01",
  "checkOut": "2026-04-04",
  "guests": 2
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "userId": "uuid",
  "roomId": "uuid",
  "hotelId": "uuid",
  "checkIn": "2026-04-01",
  "checkOut": "2026-04-04",
  "guests": 2,
  "holdId": "uuid",
  "holdExpiresAt": "2026-04-01T15:15:00Z",
  "roomType": "Standard",
  "hotelName": "Hotel Caribe Plaza",
  "roomName": "Standard",
  "location": "Cartagena, Colombia",
  "rating": 4.5,
  "nights": 3,
  "priceBreakdown": {
    "pricePerNight": "250000.00",
    "nights": 3,
    "subtotal": "750000.00",
    "vat": "142500.00",
    "tourismTax": "0",
    "serviceFee": "0",
    "total": "892500.00",
    "currency": "COP"
  },
  "createdAt": "2026-04-01T15:00:00Z"
}
```

### GET /api/v1/cart

Returns the current cart. Returns `410 Gone` if the hold has expired.

### DELETE /api/v1/cart

Releases the inventory hold and deletes the cart.

## Inter-Service Communication

| To | Method | Endpoint | Purpose |
|----|--------|----------|---------|
| inventory_service | POST | `/holds` | Create 15-min hold |
| inventory_service | DELETE | `/holds/{id}` | Release hold |
| inventory_service | GET | `/holds/{id}` | Check hold status |
| inventory_service | GET | `/rooms/{id}` | Room details |
| inventory_service | GET | `/rooms/{id}/hotel` | Hotel details |

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost.../travelhub` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `INVENTORY_SERVICE_URL` | `http://localhost:8006` | Inventory service base URL |

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8004
poetry run pytest
```
