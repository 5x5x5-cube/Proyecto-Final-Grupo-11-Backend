"""Tests for booking response enrichment with inventory and auth data."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Booking
from app.services.booking_service import build_booking_response, enrich_booking_responses

HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")


def _make_booking(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        code="BK-TEST1234",
        user_id=USER_ID,
        hotel_id=HOTEL_ID,
        room_id=ROOM_ID,
        hold_id=None,
        payment_id=None,
        guest_name=None,
        guest_email=None,
        guest_phone=None,
        check_in=date(2026, 5, 10),
        check_out=date(2026, 5, 12),
        guests=2,
        status="confirmed",
        base_price=500000,
        tax_amount=95000,
        service_fee=0,
        total_price=595000,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Booking(**defaults)


def _make_mock_client(hotel_data=None, room_data=None, user_data=None):
    async def mock_get(url, **kwargs):
        resp = MagicMock()
        if "/hotels/" in url and hotel_data is not None:
            resp.status_code = 200
            resp.json.return_value = hotel_data
        elif "/rooms/" in url and room_data is not None:
            resp.status_code = 200
            resp.json.return_value = room_data
        elif "/auth/users/" in url and user_data is not None:
            resp.status_code = 200
            resp.json.return_value = user_data
        else:
            resp.status_code = 404
            resp.json.return_value = {}
        return resp

    client = MagicMock()
    client.get = mock_get
    return client


def _patch_httpx(hotel_data=None, room_data=None, user_data=None):
    mock_client = _make_mock_client(hotel_data, room_data, user_data)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch("app.services.booking_service.httpx.AsyncClient", return_value=ctx)


async def test_enrich_adds_hotel_name():
    booking = _make_booking()
    response = build_booking_response(booking)
    assert response.hotel_name is None

    with _patch_httpx(
        hotel_data={"name": "Hotel Caribe", "city": "Cartagena", "country": "Colombia"}
    ):
        await enrich_booking_responses([response], [booking])

    assert response.hotel_name == "Hotel Caribe"
    assert response.location == "Cartagena, Colombia"


async def test_enrich_adds_room_name():
    booking = _make_booking()
    response = build_booking_response(booking)

    with _patch_httpx(room_data={"room_type": "Deluxe", "room_number": "201"}):
        await enrich_booking_responses([response], [booking])

    assert response.room_name == "Deluxe"


async def test_enrich_adds_guest_name():
    booking = _make_booking()
    response = build_booking_response(booking)

    with (
        _patch_httpx(user_data={"name": "Carlos Martinez", "email": "carlos@test.com"}),
        patch("app.services.booking_service.settings.auth_service_url", "http://auth:8000"),
    ):
        await enrich_booking_responses([response], [booking])

    assert response.guest_name == "Carlos Martinez"
    assert response.guest_email == "carlos@test.com"


async def test_enrich_does_not_overwrite_existing_guest_name():
    booking = _make_booking(guest_name="Already Set")
    response = build_booking_response(booking)

    with _patch_httpx(user_data={"name": "Different", "email": "other@test.com"}):
        await enrich_booking_responses([response], [booking])

    assert response.guest_name == "Already Set"


async def test_enrich_handles_failure_gracefully():
    booking = _make_booking()
    response = build_booking_response(booking)

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.booking_service.httpx.AsyncClient", return_value=ctx):
        await enrich_booking_responses([response], [booking])

    assert response.hotel_name is None
    assert response.room_name is None


async def test_enrich_all_fields_together():
    booking = _make_booking()
    response = build_booking_response(booking)

    with (
        _patch_httpx(
            hotel_data={"name": "Grand Hotel", "city": "Bogota", "country": "Colombia"},
            room_data={"room_type": "Suite"},
            user_data={"name": "Ana Lopez", "email": "ana@test.com"},
        ),
        patch("app.services.booking_service.settings.auth_service_url", "http://auth:8000"),
    ):
        await enrich_booking_responses([response], [booking])

    assert response.hotel_name == "Grand Hotel"
    assert response.location == "Bogota, Colombia"
    assert response.room_name == "Suite"
    assert response.guest_name == "Ana Lopez"
