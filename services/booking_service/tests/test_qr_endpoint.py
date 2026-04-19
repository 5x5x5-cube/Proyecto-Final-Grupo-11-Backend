"""Tests for QR code generation endpoint."""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_db
from app.main import app
from app.models import Booking

BOOKING_ID = uuid.UUID("e1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("c2000000-0000-0000-0000-000000000002")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")

USER_HEADER = {"X-User-Id": str(USER_ID)}
OTHER_USER_HEADER = {"X-User-Id": str(OTHER_USER_ID)}
BASE_URL = "http://test"


def _make_booking(
    status="confirmed", user_id=USER_ID, check_in_days_offset=1, guest_name="John Doe"
):
    """Create a test booking with configurable parameters."""
    return Booking(
        id=BOOKING_ID,
        code="BK-TEST1234",
        user_id=user_id,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        check_in=date.today() + timedelta(days=check_in_days_offset),
        check_out=date.today() + timedelta(days=check_in_days_offset + 2),
        guests=2,
        status=status,
        base_price=500000.0,
        tax_amount=95000.0,
        service_fee=0.0,
        total_price=595000.0,
        currency="COP",
        guest_name=guest_name,
        guest_email="john@example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _mock_db(booking):
    """Create a mock database session."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = booking
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


async def _get_qr(booking_id=BOOKING_ID, headers=None):
    """Helper to make GET request to QR endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        return await client.get(f"/api/v1/bookings/{booking_id}/qr", headers=headers or USER_HEADER)


async def test_generate_qr_success():
    """Should return 200 with valid QR token for confirmed booking."""
    booking = _make_booking()
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert "qrCode" in body
    assert body["bookingId"] == str(BOOKING_ID)
    assert body["guestName"] == "John Doe"

    # Verify JWT token is valid
    decoded = jwt.decode(
        body["qrCode"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert decoded["booking_id"] == str(BOOKING_ID)
    assert decoded["user_id"] == str(USER_ID)
    assert decoded["guest_name"] == "John Doe"
    assert "exp" in decoded
    assert "iat" in decoded


async def test_generate_qr_missing_header():
    """Should return 401 when X-User-Id header is missing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"/api/v1/bookings/{BOOKING_ID}/qr")

    assert resp.status_code == 401


async def test_generate_qr_booking_not_found():
    """Should return 404 when booking does not exist."""
    app.dependency_overrides[get_db] = lambda: _mock_db(None)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_generate_qr_wrong_user():
    """Should return 403 when booking belongs to another user."""
    booking = _make_booking(user_id=OTHER_USER_ID)
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


async def test_generate_qr_pending_booking():
    """Should return 400 when booking is not confirmed."""
    booking = _make_booking(status="pending")
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "confirmed" in resp.json()["detail"].lower()


async def test_generate_qr_cancelled_booking():
    """Should return 400 when booking is cancelled."""
    booking = _make_booking(status="cancelled")
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


async def test_generate_qr_check_in_too_far():
    """Should return 400 when check-in is more than 3 days away."""
    booking = _make_booking(check_in_days_offset=5)
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "3 days" in resp.json()["detail"]


async def test_generate_qr_check_in_too_past():
    """Should return 400 when check-in was more than 3 days ago."""
    booking = _make_booking(check_in_days_offset=-5)
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400


async def test_generate_qr_within_valid_window():
    """Should succeed when check-in is within ±3 days."""
    for offset in [-3, -2, -1, 0, 1, 2, 3]:
        booking = _make_booking(check_in_days_offset=offset)
        app.dependency_overrides[get_db] = lambda: _mock_db(booking)
        try:
            resp = await _get_qr()
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, f"Failed for offset {offset}"


async def test_generate_qr_no_guest_name():
    """Should use 'Guest' as default when guest_name is None."""
    booking = _make_booking(guest_name=None)
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        resp = await _get_qr()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["guestName"] == "Guest"

    decoded = jwt.decode(
        body["qrCode"], settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )
    assert decoded["guest_name"] == "Guest"
