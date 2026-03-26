# Inventory Service — Architecture

## Overview

The Inventory Service manages hotel, room, and availability data. Its primary responsibility is handling **room holds** — temporary 15-minute reservations that block availability while a user completes payment. It implements a dual-lock concurrency pattern: **PostgreSQL `SELECT FOR UPDATE`** for database-level integrity + **Redis TTL keys** for distributed fast-path conflict detection.

## Domain Model

```
Hotel (1) ──── (*) Room (1) ──── (*) Availability (per date)
                     │
                     └──── (*) Hold (active reservation hold)
```

| Entity | Owned by this service? | Description |
|--------|----------------------|-------------|
| **Hotel** | Yes | Property listing (name, city, rating) |
| **Room** | Yes | Room type within a hotel (capacity, price, amenities) |
| **Availability** | Yes | Per-room, per-date available quantity |
| **Hold** | Yes | Active 15-min reservation hold linked to a user |

> `user_id` in Hold is a UUID reference (no FK) — the User entity is owned by `auth_service`.

## Database Schema

All tables live in the shared `travelhub` PostgreSQL database.

### `hotels`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| name | VARCHAR(255) | NOT NULL |
| description | TEXT | |
| city | VARCHAR(100) | |
| country | VARCHAR(100) | |
| rating | DECIMAL(2,1) | |
| status | VARCHAR(20) | default `'active'` |
| created_at | TIMESTAMPTZ | |

### `rooms`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| hotel_id | UUID | FK → hotels.id |
| room_type | VARCHAR(50) | NOT NULL |
| room_number | VARCHAR(20) | |
| capacity | INTEGER | NOT NULL |
| price_per_night | DECIMAL(10,2) | NOT NULL |
| tax_rate | DECIMAL(5,4) | default `0.19` (19% IVA) |
| description | TEXT | |
| amenities | JSONB | |
| total_quantity | INTEGER | default `1` |
| created_at | TIMESTAMPTZ | |

### `availability`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| room_id | UUID | FK → rooms.id |
| date | DATE | NOT NULL |
| total_quantity | INTEGER | |
| available_quantity | INTEGER | decremented on hold |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |
| | | **UNIQUE(room_id, date)** |

### `holds`
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK (also used as Redis key) |
| room_id | UUID | FK → rooms.id |
| user_id | UUID | cross-service ref (no FK) |
| check_in | DATE | |
| check_out | DATE | |
| status | VARCHAR(20) | `active` / `converted` / `expired` |
| expires_at | TIMESTAMPTZ | created_at + 15 min |
| created_at | TIMESTAMPTZ | |

Alembic version table: `alembic_version_inventory` (isolated from other services sharing the same DB).

## Redis Key Patterns

| Key | TTL | Purpose |
|-----|-----|---------|
| `hold:{holdId}` | 900s (15 min) | Main hold record (JSON with room, user, dates) |
| `room_hold:{roomId}:{YYYY-MM-DD}` | 900s (15 min) | Per-date conflict detection key. One per night in the stay. |

**Hold JSON value:**
```json
{
  "holdId": "uuid",
  "roomId": "uuid",
  "userId": "uuid",
  "checkIn": "2026-04-01",
  "checkOut": "2026-04-03",
  "createdAt": "2026-03-26T02:05:04Z"
}
```

## API Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/rooms/{id}` | Room details | 200 / 404 |
| GET | `/rooms/{id}/hotel` | Hotel for a room | 200 / 404 |
| GET | `/rooms/{id}/availability?checkIn&checkOut` | Availability per date | 200 / 404 |
| GET | `/holds/check/{roomId}?checkIn&checkOut&userId` | Quick Redis hold check | 200 |
| POST | `/holds` | Create a 15-min hold | 201 / 409 |
| GET | `/holds/{id}` | Hold status + remaining TTL | 200 / 404 |
| DELETE | `/holds/{id}` | Release hold + restore inventory | 204 / 404 |
| GET | `/health` | Health check | 200 |

## Sequence Diagrams

### Hold Creation

```mermaid
sequenceDiagram
    participant B as booking_service
    participant I as inventory_service
    participant DB as PostgreSQL
    participant R as Redis

    B->>I: POST /holds {roomId, userId, checkIn, checkOut}
    I->>R: GET room_hold:{roomId}:{date} (for each date)
    R-->>I: null (no existing hold)

    loop For each date in range
        I->>DB: SELECT FROM availability WHERE room_id=? AND date=? FOR UPDATE
        DB-->>I: Availability row (locked)
        I->>I: Check available_quantity > 0
        I->>DB: UPDATE availability SET available_quantity -= 1
    end

    I->>DB: INSERT INTO holds (status='active', expires_at=now+15min)
    I->>R: SET hold:{holdId} {json} EX 900
    I->>R: SET room_hold:{roomId}:{date} {json} EX 900 (for each date)
    I->>DB: COMMIT
    I-->>B: 201 {holdId, expiresAt, pricePerNight, taxRate}
```

### Hold Conflict (409)

```mermaid
sequenceDiagram
    participant B as booking_service
    participant I as inventory_service
    participant R as Redis

    B->>I: POST /holds {roomId, userId, checkIn, checkOut}
    I->>R: GET room_hold:{roomId}:{date}
    R-->>I: {"holdId": "...", "userId": "other-user"}
    I-->>B: 409 ROOM_HELD "Room is currently held by another user"
```

### Background Cleanup (Expired Holds)

```mermaid
sequenceDiagram
    participant T as Cleanup Task (every 60s)
    participant DB as PostgreSQL
    participant R as Redis

    T->>DB: SELECT * FROM holds WHERE status='active' AND expires_at < NOW()
    DB-->>T: [expired holds]

    loop For each expired hold
        T->>DB: SELECT FROM availability FOR UPDATE (per date)
        T->>DB: UPDATE availability SET available_quantity += 1
        T->>DB: UPDATE holds SET status='expired'
        T->>R: DELETE room_hold:{roomId}:{date} (belt-and-suspenders)
        T->>R: DELETE hold:{holdId}
    end

    T->>DB: COMMIT
```

## Configuration

| Env Variable | Default | Description |
|-------------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub` | PostgreSQL connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `HOLD_TTL` | `900` | Hold duration in seconds (15 min) |
| `CLEANUP_INTERVAL` | `60` | Seconds between cleanup sweeps |
