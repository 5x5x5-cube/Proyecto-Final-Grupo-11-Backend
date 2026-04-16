"""Router-level tests for hotel admin booking endpoints."""

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


# ── GET /api/v1/bookings/hotel ─────────────────────────────────────────────────

LIST_URL = "/api/v1/bookings/hotel"


def _mock_db_for_list(bookings: list, total: int, summary_rows: list):
    """
    Crea un mock de DB que responde a las 3 llamadas que hace list_hotel_bookings:
    1. SELECT COUNT(*) → scalar_one() = total
    2. SELECT status, COUNT(*) GROUP BY status → .all() = summary_rows
    3. SELECT * paginado → .scalars().all() = bookings
    """
    mock_db = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = total

    summary_result = MagicMock()
    summary_result.all.return_value = summary_rows

    paged_result = MagicMock()
    paged_result.scalars.return_value.all.return_value = bookings

    mock_db.execute = AsyncMock(side_effect=[count_result, summary_result, paged_result])
    return mock_db


async def test_list_hotel_bookings_200():
    """Retorna 200 con datos y resumen cuando hay reservas."""
    booking = _make_booking(status="confirmed")
    summary_rows = [("confirmed", 1)]
    mock_db = _mock_db_for_list([booking], total=1, summary_rows=summary_rows)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["limit"] == 10
    assert len(body["data"]) == 1
    assert body["data"][0]["status"] == "confirmed"
    assert body["summary"]["confirmed"] == 1
    assert body["summary"]["pending"] == 0


async def test_list_hotel_bookings_empty_200():
    """Retorna 200 con lista vacía cuando no hay reservas."""
    mock_db = _mock_db_for_list([], total=0, summary_rows=[])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["data"] == []
    assert body["summary"]["total"] == 0


async def test_list_hotel_bookings_filter_status_200():
    """El parámetro status se acepta y retorna 200."""
    mock_db = _mock_db_for_list([], total=0, summary_rows=[])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, params={"status": "pending"}, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


async def test_list_hotel_bookings_filter_invalid_status_422():
    """Un status no válido retorna 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(LIST_URL, params={"status": "unknown"}, headers=HOTEL_HEADER)

    assert resp.status_code == 422


async def test_list_hotel_bookings_filter_date_range_200():
    """Los filtros checkInFrom y checkInTo se aceptan correctamente."""
    mock_db = _mock_db_for_list([], total=0, summary_rows=[])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(
                LIST_URL,
                params={"checkInFrom": "2026-03-01", "checkInTo": "2026-03-31"},
                headers=HOTEL_HEADER,
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


async def test_list_hotel_bookings_filter_code_200():
    """El filtro code (búsqueda parcial) se acepta correctamente."""
    booking = _make_booking(status="confirmed")
    mock_db = _mock_db_for_list([booking], total=1, summary_rows=[("confirmed", 1)])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, params={"code": "BK-AB"}, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


async def test_list_hotel_bookings_pagination_200():
    """Los parámetros page y limit se aceptan y se reflejan en la respuesta."""
    mock_db = _mock_db_for_list([], total=0, summary_rows=[])

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, params={"page": 2, "limit": 5}, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 2
    assert body["limit"] == 5


async def test_list_hotel_bookings_missing_header_401():
    """Sin X-Hotel-Id retorna 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(LIST_URL)

    assert resp.status_code == 401


async def test_list_hotel_bookings_summary_multi_status():
    """El resumen refleja correctamente múltiples estados."""
    bookings = [_make_booking(status="confirmed"), _make_booking(status="pending")]
    summary_rows = [("confirmed", 2), ("pending", 1)]
    mock_db = _mock_db_for_list(bookings, total=3, summary_rows=summary_rows)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(LIST_URL, headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    summary = resp.json()["summary"]
    assert summary["confirmed"] == 2
    assert summary["pending"] == 1
    assert summary["cancelled"] == 0
    assert summary["total"] == 3


# ── GET /api/v1/bookings/hotel/{booking_id} ───────────────────────────────────


async def test_get_hotel_booking_200():
    """Retorna 200 con los datos de la reserva cuando existe."""
    booking = _make_booking(status="confirmed")
    app.dependency_overrides[get_db] = lambda: _mock_db(booking)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}", headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["id"] == str(BOOKING_ID)
    assert resp.json()["status"] == "confirmed"


async def test_get_hotel_booking_not_found_404():
    """Retorna 404 cuando la reserva no pertenece al hotel o no existe."""
    app.dependency_overrides[get_db] = lambda: _mock_db(None)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
            resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}", headers=HOTEL_HEADER)
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_get_hotel_booking_missing_header_401():
    """Sin X-Hotel-Id retorna 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as client:
        resp = await client.get(f"/api/v1/bookings/hotel/{BOOKING_ID}")

    assert resp.status_code == 401
