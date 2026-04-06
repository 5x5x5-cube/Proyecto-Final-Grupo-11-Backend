"""Tests para HU3.3 — detalle de reserva con datos del huésped y timeline."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models import Booking
from app.schemas import CreateBookingRequest
from app.services.booking_service import _build_timeline, build_booking_response, create_booking

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

BOOKING_ID = uuid.UUID("e2000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")

HOTEL_HEADER = {"X-Hotel-Id": str(HOTEL_ID)}
BASE_URL = "http://test"
CHECK_IN = date.today() + timedelta(days=1)
CHECK_OUT = date.today() + timedelta(days=3)
NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_booking(
    status: str = "confirmed",
    guest_name: str | None = "Ana Torres",
    guest_email: str | None = "ana@email.com",
    guest_phone: str | None = "+57 310 000 0000",
    hold_id: uuid.UUID | None = HOLD_ID,
) -> Booking:
    return Booking(
        id=BOOKING_ID,
        code="BK-HU33TEST",
        user_id=USER_ID,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        hold_id=hold_id,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_phone=guest_phone,
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=2,
        status=status,
        base_price=500000.0,
        tax_amount=95000.0,
        service_fee=0.0,
        total_price=595000.0,
        currency="COP",
        created_at=NOW,
        updated_at=NOW,
    )


def _mock_db_single(booking: Booking | None) -> AsyncMock:
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = booking
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    return mock_db


def _make_fake_refresh():
    async def fake_refresh(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.code is None:
            obj.code = "BK-HU33TEST"
        if obj.currency is None:
            obj.currency = "COP"
        if obj.created_at is None:
            obj.created_at = NOW
        if obj.updated_at is None:
            obj.updated_at = NOW

    return fake_refresh


# ---------------------------------------------------------------------------
# Tests de _build_timeline
# ---------------------------------------------------------------------------


def test_timeline_confirmed_booking_has_three_events():
    """Una reserva confirmada con hold genera 3 eventos: hold, created, confirmed."""
    booking = _make_booking(status="confirmed")
    events = _build_timeline(booking)

    assert len(events) == 3
    assert events[0].event == "hold_created"
    assert events[1].event == "booking_created"
    assert events[2].event == "confirmed"


def test_timeline_pending_booking_has_two_events():
    """Una reserva pendiente con hold genera 2 eventos: hold y created."""
    booking = _make_booking(status="pending")
    events = _build_timeline(booking)

    assert len(events) == 2
    assert events[0].event == "hold_created"
    assert events[1].event == "booking_created"


def test_timeline_rejected_booking_has_three_events():
    """Una reserva rechazada genera 3 eventos incluyendo 'rejected'."""
    booking = _make_booking(status="rejected")
    events = _build_timeline(booking)

    assert len(events) == 3
    assert events[2].event == "rejected"


def test_timeline_cancelled_booking_has_three_events():
    """Una reserva cancelada genera 3 eventos incluyendo 'cancelled'."""
    booking = _make_booking(status="cancelled")
    events = _build_timeline(booking)

    assert len(events) == 3
    assert events[2].event == "cancelled"


def test_timeline_without_hold_omits_hold_event():
    """Sin hold_id no se genera el evento hold_created."""
    booking = _make_booking(status="confirmed", hold_id=None)
    events = _build_timeline(booking)

    assert len(events) == 2
    assert all(e.event != "hold_created" for e in events)


def test_timeline_events_have_timestamps():
    """Todos los eventos del timeline incluyen un timestamp."""
    booking = _make_booking(status="confirmed")
    events = _build_timeline(booking)

    for event in events:
        assert isinstance(event.timestamp, datetime)


def test_timeline_events_have_descriptions():
    """Todos los eventos del timeline incluyen descripción no vacía."""
    booking = _make_booking(status="confirmed")
    events = _build_timeline(booking)

    for event in events:
        assert event.description != ""


# ---------------------------------------------------------------------------
# Tests de build_booking_response — campos del huésped
# ---------------------------------------------------------------------------


def test_build_response_includes_guest_fields():
    """build_booking_response propaga los campos del huésped."""
    booking = _make_booking()
    response = build_booking_response(booking)

    assert response.guest_name == "Ana Torres"
    assert response.guest_email == "ana@email.com"
    assert response.guest_phone == "+57 310 000 0000"


def test_build_response_guest_fields_none_when_absent():
    """Los campos del huésped son None cuando no fueron provistos."""
    booking = _make_booking(guest_name=None, guest_email=None, guest_phone=None)
    response = build_booking_response(booking)

    assert response.guest_name is None
    assert response.guest_email is None
    assert response.guest_phone is None


def test_build_response_includes_timeline():
    """build_booking_response incluye el timeline derivado."""
    booking = _make_booking(status="confirmed")
    response = build_booking_response(booking)

    assert len(response.timeline) > 0
    assert response.timeline[-1].event == "confirmed"


# ---------------------------------------------------------------------------
# Tests de create_booking — persistencia de datos del huésped
# ---------------------------------------------------------------------------


async def test_create_booking_persists_guest_fields():
    """create_booking guarda los datos del huésped en el modelo."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_refresh())

    request = CreateBookingRequest(
        roomId=ROOM_ID,
        hotelId=HOTEL_ID,
        holdId=HOLD_ID,
        checkIn=CHECK_IN,
        checkOut=CHECK_OUT,
        guests=2,
        basePrice=Decimal("500000"),
        taxAmount=Decimal("95000"),
        serviceFee=Decimal("0"),
        totalPrice=Decimal("595000"),
        guestName="Ana Torres",
        guestEmail="ana@email.com",
        guestPhone="+57 310 000 0000",
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.guest_name == "Ana Torres"
    assert result.guest_email == "ana@email.com"
    assert result.guest_phone == "+57 310 000 0000"


async def test_create_booking_without_guest_fields():
    """create_booking funciona correctamente sin datos del huésped."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_refresh())

    request = CreateBookingRequest(
        roomId=ROOM_ID,
        hotelId=HOTEL_ID,
        holdId=HOLD_ID,
        checkIn=CHECK_IN,
        checkOut=CHECK_OUT,
        guests=2,
        basePrice=Decimal("500000"),
        taxAmount=Decimal("95000"),
        serviceFee=Decimal("0"),
        totalPrice=Decimal("595000"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.guest_name is None
    assert result.guest_email is None
    assert result.guest_phone is None
    assert result.status == "confirmed"


# ---------------------------------------------------------------------------
# Tests del endpoint GET /api/v1/bookings/hotel/{id} — respuesta completa
# ---------------------------------------------------------------------------


async def test_hotel_booking_detail_includes_guest_and_timeline():
    """El endpoint GET /hotel/{id} devuelve datos del huésped y timeline."""
    booking = _make_booking(status="confirmed")
    app.dependency_overrides[get_db] = lambda: _mock_db_single(booking)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}", headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["guestName"] == "Ana Torres"
    assert body["guestEmail"] == "ana@email.com"
    assert body["guestPhone"] == "+57 310 000 0000"
    assert len(body["timeline"]) == 3
    assert body["timeline"][-1]["event"] == "confirmed"


async def test_hotel_booking_detail_guest_fields_null_when_absent():
    """El endpoint devuelve guestName/Email/Phone null si no fueron registrados."""
    booking = _make_booking(guest_name=None, guest_email=None, guest_phone=None)
    app.dependency_overrides[get_db] = lambda: _mock_db_single(booking)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}", headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["guestName"] is None
    assert body["guestEmail"] is None
    assert body["guestPhone"] is None


async def test_hotel_booking_detail_pending_timeline_has_two_events():
    """El endpoint devuelve 2 eventos en el timeline para reservas pendientes."""
    booking = _make_booking(status="pending")
    app.dependency_overrides[get_db] = lambda: _mock_db_single(booking)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}", headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(resp.json()["timeline"]) == 2
