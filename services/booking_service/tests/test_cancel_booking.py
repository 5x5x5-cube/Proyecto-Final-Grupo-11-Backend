"""Tests for booking cancellation endpoint."""

import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import Booking
from app.services.payment_client import PaymentServiceError

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
    payment_id: uuid.UUID | None = None,
) -> Booking:
    """Create a test booking."""
    return Booking(
        id=booking_id or uuid.uuid4(),
        code=f"BK-TEST{uuid.uuid4().hex[:8].upper()}",
        user_id=user_id,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        payment_id=payment_id,
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


@contextmanager
def _patched_side_effects(refund_side_effect=None):
    """Patch SNS publisher and payment refund client so cancellation tests
    don't try to hit AWS or the payment_service over the network.

    Yields (refund_mock, sns_mock) for assertions. Pass refund_side_effect to
    simulate refund failures (e.g. PaymentServiceError instance).
    """
    refund_mock = AsyncMock(return_value={"status": "refunded"})
    if refund_side_effect is not None:
        refund_mock.side_effect = refund_side_effect
    sns_mock = AsyncMock(return_value=True)
    with patch("app.routers.bookings.request_refund", refund_mock), patch(
        "app.routers.bookings.sns_publisher.publish_booking_cancelled", sns_mock
    ):
        yield refund_mock, sns_mock


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
        with _patched_side_effects():
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
        with _patched_side_effects():
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
        with _patched_side_effects():
            resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(booking.id)
        assert data["status"] == "cancelled"
        assert data["code"] == booking.code
        # HU4.3 — response now includes a cancellation block
        assert "cancellation" in data
        assert "refundAmount" in data["cancellation"]
        assert "refundPercentage" in data["cancellation"]
        assert "refundStatus" in data["cancellation"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# HU4.3 — refund policy + side-effects (payment_service + SNS)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_more_than_seven_days_triggers_full_refund():
    """CA1 — cancellation with more than 7 days advance returns 100% refund."""
    payment_id = uuid.uuid4()
    booking = _make_booking(status="confirmed", check_in_days=10, payment_id=payment_id)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects() as (refund_mock, sns_mock):
            resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["cancellation"]["refundPercentage"] == 1.0
        assert data["cancellation"]["refundStatus"] == "processed"
        # 100% of 124000 = 124000
        assert data["cancellation"]["refundAmount"] == 124000
        # payment_service was called with the right amount and payment id
        refund_mock.assert_called_once()
        kwargs = refund_mock.call_args.kwargs
        assert kwargs["payment_id"] == payment_id
        assert kwargs["amount"] == 124000.00
        # SNS event published
        sns_mock.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_between_two_and_seven_days_triggers_partial_refund():
    """CA2 — cancellation between 2 and 7 days advance returns 50% refund."""
    payment_id = uuid.uuid4()
    booking = _make_booking(status="confirmed", check_in_days=5, payment_id=payment_id)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects() as (refund_mock, _):
            resp = await _cancel_booking(booking.id)
        data = resp.json()
        assert data["cancellation"]["refundPercentage"] == 0.5
        assert data["cancellation"]["refundAmount"] == 62000  # 50% of 124000
        refund_mock.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_less_than_two_days_skips_refund():
    """CA3 — cancellation with less than 2 days advance: no refund."""
    payment_id = uuid.uuid4()
    booking = _make_booking(status="confirmed", check_in_days=1, payment_id=payment_id)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects() as (refund_mock, sns_mock):
            resp = await _cancel_booking(booking.id)
        data = resp.json()
        assert data["cancellation"]["refundPercentage"] == 0.0
        assert data["cancellation"]["refundAmount"] == 0
        assert data["cancellation"]["refundStatus"] == "no_refund"
        # No refund call when amount is zero
        refund_mock.assert_not_called()
        # SNS event still published so inventory can release the room
        sns_mock.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_without_payment_id_does_not_call_payment_service():
    """If a booking has no payment_id, the refund call must be skipped."""
    booking = _make_booking(status="pending", check_in_days=10, payment_id=None)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects() as (refund_mock, sns_mock):
            resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        # Even though policy says 100%, no payment_id means no refund call
        refund_mock.assert_not_called()
        # But SNS still fires so inventory is released
        sns_mock.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_marks_refund_failed_when_payment_service_errors():
    """If payment_service rejects the refund, booking still cancels and the
    refund is recorded as failed (no rollback of the cancellation)."""
    payment_id = uuid.uuid4()
    booking = _make_booking(status="confirmed", check_in_days=10, payment_id=payment_id)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects(
            refund_side_effect=PaymentServiceError("boom", status_code=400)
        ) as (_, sns_mock):
            resp = await _cancel_booking(booking.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["cancellation"]["refundStatus"] == "failed"
        # The cancellation event still goes out so inventory liberates the room
        sns_mock.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cancel_publishes_event_with_correct_payload():
    """SNS event must carry the data inventory + notification need."""
    payment_id = uuid.uuid4()
    booking = _make_booking(status="confirmed", check_in_days=10, payment_id=payment_id)
    mock_db = _mock_db(booking)

    from app.database import get_db

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with _patched_side_effects() as (_, sns_mock):
            await _cancel_booking(booking.id)
        sns_mock.assert_called_once()
        kwargs = sns_mock.call_args.kwargs
        assert kwargs["booking_id"] == str(booking.id)
        assert kwargs["room_id"] == str(booking.room_id)
        assert kwargs["hotel_id"] == str(booking.hotel_id)
        assert kwargs["user_id"] == str(booking.user_id)
        assert kwargs["currency"] == "COP"
        assert kwargs["refund_status"] == "processed"
        assert kwargs["refund_percentage"] == 1.0
        assert kwargs["previous_status"] == "confirmed"
    finally:
        app.dependency_overrides.clear()
