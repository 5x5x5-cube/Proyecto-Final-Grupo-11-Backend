"""Router-level tests for hotel admin status update endpoint."""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models import Booking

BOOKING_ID = uuid.UUID("e1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
OTHER_HOTEL_ID = uuid.UUID("a2000000-0000-0000-0000-000000000002")
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")

CHECK_IN = date.today() + timedelta(days=1)
CHECK_OUT = date.today() + timedelta(days=3)

HOTEL_HEADER = {"X-Hotel-Id": str(HOTEL_ID)}
BASE_URL = "http://test"
STATUS_URL = f"/api/v1/bookings/hotel/{BOOKING_ID}/status"


def _make_booking(status="pending", hotel_id=None):
    return Booking(
        id=BOOKING_ID,
        code="BK-ABCD1234",
        user_id=USER_ID,
        hotel_id=hotel_id or HOTEL_ID,
        room_id=ROOM_ID,
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=2,
        status=status,
        base_price=500000.0,
        tax_amount=95000.0,
        service_fee=0.0,
        total_price=595000.0,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _mock_db(booking):
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = booking
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


async def _post(json_body, headers=None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        return await client.post(STATUS_URL, json=json_body, headers=headers or HOTEL_HEADER)


async def test_confirm_200():
    booking = _make_booking()
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _post({"action": "confirm"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


async def test_confirm_already_processed_409():
    booking = _make_booking(status="confirmed")
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _post({"action": "confirm"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409
    assert resp.json()["code"] == "BOOKING_ALREADY_PROCESSED"


async def test_reject_200():
    booking = _make_booking()
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _post({"action": "reject"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


async def test_reject_already_processed_409():
    booking = _make_booking(status="rejected")
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _post({"action": "reject"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 409


async def test_missing_header_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.post(STATUS_URL, json={"action": "confirm"})

    assert resp.status_code == 401


async def test_not_found_404():
    app.dependency_overrides[get_db] = lambda: _mock_db(None)
    try:
        resp = await _post({"action": "confirm"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_wrong_hotel_403():
    booking = _make_booking(hotel_id=OTHER_HOTEL_ID)
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _post({"action": "confirm"})
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


async def test_invalid_action_422():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.post(STATUS_URL, json={"action": "cancel"}, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422
