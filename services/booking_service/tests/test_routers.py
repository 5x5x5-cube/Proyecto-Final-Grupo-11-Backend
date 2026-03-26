import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.exceptions import InventoryServiceError
from app.main import app
from app.models import Booking
from app.redis_client import get_redis
from app.schemas import BookingResponse, PriceBreakdown

# ---------------------------------------------------------------------------
# Fixed UUIDs for predictability
# ---------------------------------------------------------------------------

BOOKING_ID = uuid.UUID("e1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

CHECK_IN = date.today() + timedelta(days=1)
CHECK_OUT = date.today() + timedelta(days=3)

VALID_PAYLOAD = {
    "roomId": str(ROOM_ID),
    "hotelId": str(HOTEL_ID),
    "checkIn": CHECK_IN.isoformat(),
    "checkOut": CHECK_OUT.isoformat(),
    "guests": 2,
    "userId": str(USER_ID),
}


def _make_booking_response() -> BookingResponse:
    """Return a fully-populated BookingResponse for mocking create_booking."""
    return BookingResponse(
        id=BOOKING_ID,
        code="BK-ABCD1234",
        userId=USER_ID,
        hotelId=HOTEL_ID,
        roomId=ROOM_ID,
        holdId=HOLD_ID,
        checkIn=CHECK_IN,
        checkOut=CHECK_OUT,
        guests=2,
        status="pending",
        totalPrice=595000.0,
        currency="COP",
        priceBreakdown=PriceBreakdown(
            pricePerNight=250000.0,
            nights=2,
            basePrice=500000.0,
            vat=95000.0,
            serviceFee=0.0,
            totalPrice=595000.0,
            currency="COP",
        ),
        holdExpiresAt=datetime.now(timezone.utc) + timedelta(minutes=15),
        createdAt=datetime.now(timezone.utc),
    )


def _make_booking_orm() -> Booking:
    """Return an ORM Booking instance for mocking DB lookups."""
    return Booking(
        id=BOOKING_ID,
        code="BK-ABCD1234",
        user_id=USER_ID,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        hold_id=HOLD_ID,
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=2,
        status="pending",
        base_price=500000.0,
        tax_amount=95000.0,
        service_fee=0.0,
        total_price=595000.0,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# POST /bookings
# ---------------------------------------------------------------------------


async def test_post_bookings_success_201():
    """POST /bookings returns 201 when create_booking succeeds."""
    mock_response = _make_booking_response()

    with patch("app.routers.bookings.create_booking", new=AsyncMock(return_value=mock_response)):
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        app.dependency_overrides[get_redis] = lambda: AsyncMock()
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/bookings", json=VALID_PAYLOAD)
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == str(BOOKING_ID)
    assert body["status"] == "pending"
    assert body["totalPrice"] == 595000.0
    assert body["currency"] == "COP"


async def test_post_bookings_conflict_409():
    """POST /bookings returns 409 when create_booking raises InventoryServiceError(409)."""
    error = InventoryServiceError("Room is being processed by another user", status_code=409)

    with patch("app.routers.bookings.create_booking", new=AsyncMock(side_effect=error)):
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        app.dependency_overrides[get_redis] = lambda: AsyncMock()
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/bookings", json=VALID_PAYLOAD)
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "INVENTORY_ERROR"
    assert "another user" in body["message"]


async def test_post_bookings_service_busy_503():
    """POST /bookings returns 503 when create_booking raises InventoryServiceError(503)."""
    error = InventoryServiceError("Server busy, please try again", status_code=503)

    with patch("app.routers.bookings.create_booking", new=AsyncMock(side_effect=error)):
        app.dependency_overrides[get_db] = lambda: AsyncMock()
        app.dependency_overrides[get_redis] = lambda: AsyncMock()
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/bookings", json=VALID_PAYLOAD)
        finally:
            app.dependency_overrides.clear()

    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "INVENTORY_ERROR"


async def test_post_bookings_validation_error_422():
    """POST /bookings returns 422 when a required field is missing."""
    incomplete_payload = {
        "hotelId": str(HOTEL_ID),
        "checkIn": CHECK_IN.isoformat(),
        "checkOut": CHECK_OUT.isoformat(),
        "guests": 2,
        "userId": str(USER_ID),
        # "roomId" is intentionally omitted
    }

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_redis] = lambda: AsyncMock()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/bookings", json=incomplete_payload)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /bookings/{id}
# ---------------------------------------------------------------------------


async def test_get_booking_detail_200():
    """GET /bookings/{id} returns 200 with booking data when the DB returns a record."""
    booking_orm = _make_booking_orm()

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = booking_orm
    mock_db.execute = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/bookings/{BOOKING_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(BOOKING_ID)
    assert body["status"] == "pending"
    assert body["userId"] == str(USER_ID)


async def test_get_booking_detail_404():
    """GET /bookings/{id} returns 404 with BOOKING_NOT_FOUND when no record exists."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/bookings/{BOOKING_ID}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "BOOKING_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /bookings
# ---------------------------------------------------------------------------


async def test_list_bookings_200():
    """GET /bookings?userId=... returns 200 with a paginated list."""
    booking_orm = _make_booking_orm()

    mock_db = AsyncMock()

    # First execute() call → scalars().all() → booking list
    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = [booking_orm]

    # Second execute() call → scalar() → total count
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db.execute = AsyncMock(side_effect=[mock_list_result, mock_count_result])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/bookings", params={"userId": str(USER_ID)})
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["limit"] == 10
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(BOOKING_ID)


async def test_list_bookings_filtered_by_status_200():
    """GET /bookings?userId=...&status=pending returns 200 with filtered results."""
    booking_orm = _make_booking_orm()

    mock_db = AsyncMock()

    mock_list_result = MagicMock()
    mock_list_result.scalars.return_value.all.return_value = [booking_orm]

    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    mock_db.execute = AsyncMock(side_effect=[mock_list_result, mock_count_result])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/bookings", params={"userId": str(USER_ID), "status": "pending"}
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["data"][0]["status"] == "pending"
