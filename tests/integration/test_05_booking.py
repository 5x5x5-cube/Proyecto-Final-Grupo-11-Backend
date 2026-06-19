"""Test 5: Booking service — create booking from hold, list, get (direct access)."""

from datetime import date, timedelta

from conftest import (
    BOOKING_URL,
    DEFAULT_USER_ID,
    HOTEL_MEDELLIN_ID,
    INVENTORY_URL,
    ROOM_CABIN_MEDELLIN_ID,
    user_headers,
)

CHECK_IN = (date.today() + timedelta(days=35)).isoformat()
CHECK_OUT = (date.today() + timedelta(days=37)).isoformat()


def _create_hold(http):
    """Helper: create a hold for the booking test."""
    r = http.post(
        f"{INVENTORY_URL}/holds",
        json={"roomId": ROOM_CABIN_MEDELLIN_ID, "checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(),
    )
    assert r.status_code == 201, f"Hold creation failed: {r.text}"
    return r.json()


def test_create_booking(http):
    hold = _create_hold(http)
    r = http.post(
        f"{BOOKING_URL}/api/v1/bookings",
        json={
            "roomId": ROOM_CABIN_MEDELLIN_ID,
            "hotelId": HOTEL_MEDELLIN_ID,
            "holdId": hold["id"],
            "checkIn": CHECK_IN,
            "checkOut": CHECK_OUT,
            "guests": 2,
            "basePrice": 400000,
            "taxAmount": 76000,
            "serviceFee": 20000,
            "totalPrice": 496000,
        },
        headers=user_headers(),
    )
    assert r.status_code == 201, f"Booking creation failed: {r.text}"
    booking = r.json()
    assert booking["roomId"] == ROOM_CABIN_MEDELLIN_ID
    assert booking["hotelId"] == HOTEL_MEDELLIN_ID
    assert booking["userId"] == DEFAULT_USER_ID
    assert booking["status"] == "confirmed"
    assert booking["code"].startswith("BK-")
    assert booking["currency"] == "COP"

    test_create_booking.booking_id = booking["id"]


def test_get_booking(http):
    booking_id = test_create_booking.booking_id
    r = http.get(f"{BOOKING_URL}/api/v1/bookings/{booking_id}", headers=user_headers())
    assert r.status_code == 200
    booking = r.json()
    assert booking["id"] == booking_id
    assert booking["status"] == "confirmed"


def test_list_bookings(http):
    r = http.get(f"{BOOKING_URL}/api/v1/bookings", headers=user_headers())
    assert r.status_code == 200
    data = r.json()
    bookings = data if isinstance(data, list) else data.get("data", data.get("items", []))
    assert len(bookings) >= 1
    ids = [b["id"] for b in bookings]
    assert test_create_booking.booking_id in ids


def test_list_bookings_filter_by_status(http):
    r = http.get(
        f"{BOOKING_URL}/api/v1/bookings",
        params={"status": "confirmed"},
        headers=user_headers(),
    )
    assert r.status_code == 200


def test_booking_not_found(http):
    r = http.get(
        f"{BOOKING_URL}/api/v1/bookings/00000000-0000-0000-0000-000000000000",
        headers=user_headers(),
    )
    assert r.status_code == 404
