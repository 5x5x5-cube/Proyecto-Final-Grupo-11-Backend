# Inventory Service

Manages hotel, room, and availability data. Handles 15-minute room holds using a dual-lock pattern: PostgreSQL `SELECT FOR UPDATE` for DB integrity + Redis TTL keys for fast conflict detection.

See [ARCHITECTURE.md](ARCHITECTURE.md) for full details.

## Endpoints

All hold endpoints that require user identification use the `X-User-Id` header (UUID).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/rooms/{id}` | Room details |
| GET | `/rooms/{id}/hotel` | Hotel for a room |
| GET | `/rooms/{id}/availability` | Availability per date |
| POST | `/holds` | Create a 15-min hold (requires `X-User-Id`) |
| GET | `/holds/{id}` | Hold status + TTL |
| GET | `/holds/check/{roomId}` | Quick hold check (requires `X-User-Id`) |
| DELETE | `/holds/{id}` | Release hold + restore inventory |
| GET | `/health` | Health check |

## Development

```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8006
poetry run pytest
```
