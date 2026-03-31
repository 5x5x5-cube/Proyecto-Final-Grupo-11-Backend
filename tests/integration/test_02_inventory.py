"""Test 2: Inventory service — hotels, rooms, availability (direct access)."""

from datetime import date, timedelta

from conftest import (
    HOTEL_BOGOTA_ID,
    HOTEL_CARIBE_ID,
    HOTEL_MEDELLIN_ID,
    INVENTORY_URL,
    ROOM_CABIN_MEDELLIN_ID,
    ROOM_STANDARD_BOGOTA_ID,
    ROOM_STANDARD_CARIBE_ID,
)

# ── Hotels ──────────────────────────────────────────────────────────────


def test_list_hotels(http):
    r = http.get(f"{INVENTORY_URL}/hotels")
    assert r.status_code == 200
    hotels = r.json()
    assert len(hotels) >= 3
    names = {h["name"] for h in hotels}
    assert "Hotel Caribe Plaza" in names
    assert "Bogota Grand Hotel" in names
    assert "Medellin Eco Resort" in names


def test_get_hotel_by_id(http):
    r = http.get(f"{INVENTORY_URL}/hotels/{HOTEL_CARIBE_ID}")
    assert r.status_code == 200
    hotel = r.json()
    assert hotel["name"] == "Hotel Caribe Plaza"
    assert hotel["city"] == "Cartagena"


def test_get_hotel_not_found(http):
    r = http.get(f"{INVENTORY_URL}/hotels/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ── Rooms ───────────────────────────────────────────────────────────────


def test_get_room_by_id(http):
    r = http.get(f"{INVENTORY_URL}/rooms/{ROOM_STANDARD_CARIBE_ID}")
    assert r.status_code == 200
    room = r.json()
    assert room["room_type"] == "Standard"
    assert room["hotel_id"] == HOTEL_CARIBE_ID


def test_get_room_hotel(http):
    r = http.get(f"{INVENTORY_URL}/rooms/{ROOM_STANDARD_CARIBE_ID}/hotel")
    assert r.status_code == 200
    hotel = r.json()
    assert hotel["name"] == "Hotel Caribe Plaza"


# ── Availability ────────────────────────────────────────────────────────


def test_check_availability_available(http):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    day_after = (date.today() + timedelta(days=3)).isoformat()
    r = http.get(
        f"{INVENTORY_URL}/rooms/{ROOM_STANDARD_BOGOTA_ID}/availability",
        params={"checkIn": tomorrow, "checkOut": day_after},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_available"] is True
    assert data["room_id"] == ROOM_STANDARD_BOGOTA_ID
    assert len(data["dates"]) == 2  # 2 nights


def test_check_availability_returns_dates(http):
    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=10)).isoformat()
    r = http.get(
        f"{INVENTORY_URL}/rooms/{ROOM_CABIN_MEDELLIN_ID}/availability",
        params={"checkIn": start, "checkOut": end},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["dates"]) == 5
    for d in data["dates"]:
        assert d["available_quantity"] > 0
