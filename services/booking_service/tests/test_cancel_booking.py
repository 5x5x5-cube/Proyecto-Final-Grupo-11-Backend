"""Tests for booking cancellation endpoint."""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import Booking

BASE_URL = "http://test"
USER_ID = uuid.uuid4()
OTHER_USER_ID = uuid.uuid4()
HOTEL_ID = uuid.uuid4()
ROOM_ID = uuid.uuid4()


def _make_booking(
    booking_id: uuid.UUID | None = None,
    user_id: uuid.UUID = USER_ID,
    status: str = "confirmed",
    check_in_days: int = 7,
) -> Booking:
    """Create a test booking."""
    return Booking(
        id=booking_id or uuid.uuid4(),
        code=f"BK-TEST{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        guest_name="Test User",
        guest_email="test@example.com",
        check_in=date.today() + timedelta(days=check_in_days),
        check_out=date.today() + timedelta(days=check_in_days + 3),
        guests=2,
        status=status,
        base_price=100000,
        tax_amount=19000,
        service_fee=5000,
        total_price=124000,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _mock_db(booking: Booking | None = None):
    """Create a mock database session."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = booking
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


async def _cancel_booking(booking_id: uuid.UUID, user_id: uuid.UUID = USER_ID):
    """Helper to call cancel endpoint."""
    headers = {"X-User-Id": str(user_id)}
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        return await client.post(f"/api/v1/bookings/{booking_id}/cancel", headers=headers)


@pytest.mark.asyncio
async def test_cancel_confirmed_booking_success():
    """Should successfully cancel a confirmed booking."""
    booking = _make_booking(status="confirmed")
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        assert booking.status == "cancelled"
        mock_db.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_pending_booking_success():
    """Should successfully cancel a pending booking."""
    booking = _make_booking(status="pending")
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        assert booking.status == "cancelled"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_booking_not_found():
    """Should return 404 when booking doesn't exist."""
    mock_db = _mock_db(None)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(uuid.uuid4())
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_booking_wrong_user():
    """Should return 403 when user doesn't own the booking."""
    booking = _make_booking(user_id=OTHER_USER_ID)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id, user_id=USER_ID)
        assert resp.status_code == 403
        assert "permission" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_already_cancelled_booking():
    """Should return 400 when booking is already cancelled."""
    booking = _make_booking(status="cancelled")
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id)
        assert resp.status_code == 400
        assert "already cancelled" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_booking_invalid_status():
    """Should return 400 when trying to cancel booking with invalid status."""
    booking = _make_booking(status="completed")
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id)
        assert resp.status_code == 400
        assert "cannot cancel" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_booking_missing_user_header():
    """Should return 401 when X-User-Id header is missing."""
    booking = _make_booking()
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.post(f"/api/v1/bookings/{booking.id}/cancel")
        assert resp.status_code == 401
        assert "required" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_booking_returns_updated_booking():
    """Should return the updated booking with cancelled status."""
    booking = _make_booking(status="confirmed")
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(booking.id)
        assert data["status"] == "cancelled"
        assert data["code"] == booking.code
    finally:
        app.dependency_overrides.clear()
