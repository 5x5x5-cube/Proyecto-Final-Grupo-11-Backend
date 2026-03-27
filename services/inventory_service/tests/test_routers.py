"""
Integration tests for the rooms and holds routers.

Strategy: dependency_overrides inject mock DB/Redis into the app, and service
functions are patched at the router import site so we test the full
router → exception-handler pipeline without touching any real database or
Redis instance.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.exceptions import HoldNotFoundError, RoomHeldError, RoomNotFoundError, RoomUnavailableError
from app.main import app
from app.models import Availability, Hold, Room
from app.redis_client import get_redis

# ---------------------------------------------------------------------------
# Fixed UUIDs for predictable assertions
# ---------------------------------------------------------------------------
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("e1000000-0000-0000-0000-000000000002")

CHECK_IN = date(2026, 4, 1)
CHECK_OUT = date(2026, 4, 3)

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)
EXPIRES_AT = NOW + timedelta(minutes=15)


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_room():
    return Room(
        id=ROOM_ID,
        hotel_id=HOTEL_ID,
        room_type="Standard",
        room_number="101",
        capacity=2,
        price_per_night=250000,
        tax_rate=0.19,
        total_quantity=1,
        created_at=NOW,
    )


def make_hold():
    hold = Hold(
        id=HOLD_ID,
        room_id=ROOM_ID,
        user_id=USER_ID,
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        status="active",
        expires_at=EXPIRES_AT,
        created_at=NOW,
    )
    # Extra attributes attached by create_hold before returning
    hold.price_per_night = 250000.0
    hold.tax_rate = 0.19
    hold.room_type = "Standard"
    return hold


def make_availability_row(d: date, qty: int = 1):
    return Availability(
        id=uuid.uuid4(),
        room_id=ROOM_ID,
        date=d,
        total_quantity=1,
        available_quantity=qty,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
async def client(mock_db, mock_redis):
    """AsyncClient with dependency overrides installed; tears down after test."""
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Room router tests
# ---------------------------------------------------------------------------


async def test_get_room_200(client):
    """GET /rooms/{id} returns 200 and room data when room exists."""
    room = make_room()

    with patch("app.routers.rooms.get_room", new=AsyncMock(return_value=room)):
        response = await client.get(f"/rooms/{ROOM_ID}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(ROOM_ID)
    assert body["room_type"] == "Standard"
    assert body["capacity"] == 2


async def test_get_room_404(client):
    """GET /rooms/{id} returns 404 ROOM_NOT_FOUND when room does not exist."""
    with patch(
        "app.routers.rooms.get_room",
        new=AsyncMock(side_effect=RoomNotFoundError(str(ROOM_ID))),
    ):
        response = await client.get(f"/rooms/{ROOM_ID}")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "ROOM_NOT_FOUND"
    assert str(ROOM_ID) in body["message"]


async def test_get_room_availability_200(client):
    """GET /rooms/{id}/availability returns 200 with date list."""
    rows = [
        make_availability_row(date(2026, 4, 1)),
        make_availability_row(date(2026, 4, 2)),
    ]

    with patch("app.routers.rooms.check_availability", new=AsyncMock(return_value=rows)):
        response = await client.get(
            f"/rooms/{ROOM_ID}/availability",
            params={"checkIn": "2026-04-01", "checkOut": "2026-04-03"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["room_id"] == str(ROOM_ID)
    assert body["is_available"] is True
    assert len(body["dates"]) == 2
    assert body["dates"][0]["date"] == "2026-04-01"


async def test_get_room_availability_unavailable_propagates_409(client):
    """GET /rooms/{id}/availability propagates RoomUnavailableError → 409."""
    with patch(
        "app.routers.rooms.check_availability",
        new=AsyncMock(side_effect=RoomUnavailableError(str(ROOM_ID), ["2026-04-01", "2026-04-02"])),
    ):
        response = await client.get(
            f"/rooms/{ROOM_ID}/availability",
            params={"checkIn": "2026-04-01", "checkOut": "2026-04-03"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "ROOM_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Holds router tests
# ---------------------------------------------------------------------------


async def test_create_hold_201(client):
    """POST /holds returns 201 with hold data on success."""
    hold = make_hold()

    with patch("app.routers.holds.create_hold", new=AsyncMock(return_value=hold)):
        response = await client.post(
            "/holds",
            json={
                "roomId": str(ROOM_ID),
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == str(HOLD_ID)
    assert body["room_id"] == str(ROOM_ID)
    assert body["status"] == "active"
    assert body["price_per_night"] == 250000.0
    assert body["room_type"] == "Standard"


async def test_create_hold_401_missing_user_id_header(client):
    """POST /holds returns 401 when X-User-Id header is missing."""
    response = await client.post(
        "/holds",
        json={
            "roomId": str(ROOM_ID),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
        },
    )

    assert response.status_code == 401


async def test_create_hold_401_invalid_user_id_header(client):
    """POST /holds returns 401 when X-User-Id header is not a valid UUID."""
    response = await client.post(
        "/holds",
        json={
            "roomId": str(ROOM_ID),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
        },
        headers={"X-User-Id": "not-a-uuid"},
    )

    assert response.status_code == 401


async def test_create_hold_409_room_held(client):
    """POST /holds returns 409 ROOM_HELD when room is held by another user."""
    with patch(
        "app.routers.holds.create_hold",
        new=AsyncMock(side_effect=RoomHeldError(str(ROOM_ID), str(OTHER_USER_ID))),
    ):
        response = await client.post(
            "/holds",
            json={
                "roomId": str(ROOM_ID),
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "ROOM_HELD"


async def test_create_hold_409_room_unavailable(client):
    """POST /holds returns 409 ROOM_UNAVAILABLE when no inventory for dates."""
    with patch(
        "app.routers.holds.create_hold",
        new=AsyncMock(side_effect=RoomUnavailableError(str(ROOM_ID), ["2026-04-01", "2026-04-02"])),
    ):
        response = await client.post(
            "/holds",
            json={
                "roomId": str(ROOM_ID),
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "ROOM_UNAVAILABLE"
    assert body["details"] is not None
    assert "2026-04-01" in body["details"][0]["dates"]


async def test_delete_hold_204(client):
    """DELETE /holds/{id} returns 204 on successful release."""
    with patch("app.routers.holds.release_hold", new=AsyncMock(return_value=None)):
        response = await client.delete(f"/holds/{HOLD_ID}")

    assert response.status_code == 204
    assert response.content == b""


async def test_delete_hold_404(client):
    """DELETE /holds/{id} returns 404 HOLD_NOT_FOUND when hold does not exist."""
    with patch(
        "app.routers.holds.release_hold",
        new=AsyncMock(side_effect=HoldNotFoundError(str(HOLD_ID))),
    ):
        response = await client.delete(f"/holds/{HOLD_ID}")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "HOLD_NOT_FOUND"
    assert str(HOLD_ID) in body["message"]


async def test_check_hold_not_held(client, mock_db):
    """GET /holds/check/{room_id} returns held=false when no hold exists."""
    check_result = {"held": False, "holder_id": None, "hold_id": None}

    with patch("app.routers.holds.check_hold", new=AsyncMock(return_value=check_result)):
        response = await client.get(
            f"/holds/check/{ROOM_ID}",
            params={
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["held"] is False
    assert body["holder_id"] is None
    assert body["hold_id"] is None


async def test_check_hold_held_by_other(client, mock_db):
    """GET /holds/check/{room_id} returns held=true with holder info when held by another user."""
    check_result = {
        "held": True,
        "holder_id": OTHER_USER_ID,
        "hold_id": HOLD_ID,
    }

    # Mock the DB lookup for expires_at
    hold_record = make_hold()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = hold_record
    mock_db.execute.return_value = result_mock

    with patch("app.routers.holds.check_hold", new=AsyncMock(return_value=check_result)):
        response = await client.get(
            f"/holds/check/{ROOM_ID}",
            params={
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["held"] is True
    assert body["holder_id"] == str(OTHER_USER_ID)
    assert body["hold_id"] == str(HOLD_ID)


async def test_check_hold_401_missing_user_id_header(client):
    """GET /holds/check/{room_id} returns 401 when X-User-Id header is missing."""
    response = await client.get(
        f"/holds/check/{ROOM_ID}",
        params={
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
        },
    )

    assert response.status_code == 401


async def test_check_hold_returns_expires_at(client, mock_db):
    """GET /holds/check/{room_id} includes expires_at in the response when hold is found."""
    check_result = {
        "held": True,
        "holder_id": USER_ID,
        "hold_id": HOLD_ID,
        "same_user": True,
    }

    hold_record = make_hold()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = hold_record
    mock_db.execute.return_value = result_mock

    with patch("app.routers.holds.check_hold", new=AsyncMock(return_value=check_result)):
        response = await client.get(
            f"/holds/check/{ROOM_ID}",
            params={
                "checkIn": "2026-04-01",
                "checkOut": "2026-04-03",
            },
            headers={"X-User-Id": str(USER_ID)},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["held"] is True
    assert body["expires_at"] is not None
