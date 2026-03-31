"""Test 8: End-to-end booking flow through the gateway.

Simulates a real user journey:
1. Browse hotels (search)
2. Check availability (inventory)
3. Add to cart (cart + hold)
4. Confirm booking (booking)
5. Verify booking appears in list
"""

from datetime import date, timedelta

from conftest import (
    DEFAULT_USER_ID,
    GATEWAY_URL,
    HOTEL_CARIBE_ID,
    INVENTORY_URL,
    ROOM_STANDARD_CARIBE_ID,
    user_headers,
)

CHECK_IN = (date.today() + timedelta(days=45)).isoformat()
CHECK_OUT = (date.today() + timedelta(days=47)).isoformat()


def test_e2e_booking_flow(http):
    headers = user_headers()

    # ── Step 1: Check availability ───────────────────────────────────
    r = http.get(
        f"{INVENTORY_URL}/rooms/{ROOM_STANDARD_CARIBE_ID}/availability",
        params={"checkIn": CHECK_IN, "checkOut": CHECK_OUT},
    )
    assert r.status_code == 200, f"Availability check failed: {r.text}"
    avail = r.json()
    assert avail["is_available"] is True, "Room should be available"

    # ── Step 2: Add to cart (creates hold) ───────────────────────────
    r = http.put(
        f"{GATEWAY_URL}/api/v1/cart",
        json={
            "roomId": ROOM_STANDARD_CARIBE_ID,
            "hotelId": HOTEL_CARIBE_ID,
            "checkIn": CHECK_IN,
            "checkOut": CHECK_OUT,
            "guests": 2,
        },
        headers=headers,
    )
    assert r.status_code in (200, 201), f"Cart upsert failed: {r.text}"
    cart = r.json()
    hold_id = cart["holdId"]
    assert hold_id is not None, "Cart should have a hold"

    # ── Step 3: Verify cart is retrievable ───────────────────────────
    r = http.get(f"{GATEWAY_URL}/api/v1/cart", headers=headers)
    assert r.status_code == 200, f"Get cart failed: {r.text}"
    assert r.json()["holdId"] == hold_id

    # ── Step 4: Create booking ───────────────────────────────────────
    r = http.post(
        f"{GATEWAY_URL}/api/v1/bookings",
        json={
            "roomId": ROOM_STANDARD_CARIBE_ID,
            "hotelId": HOTEL_CARIBE_ID,
            "holdId": hold_id,
            "checkIn": CHECK_IN,
            "checkOut": CHECK_OUT,
            "guests": 2,
            "basePrice": 500000,
            "taxAmount": 95000,
            "serviceFee": 25000,
            "totalPrice": 620000,
        },
        headers=headers,
    )
    assert r.status_code == 201, f"Booking creation failed: {r.text}"
    booking = r.json()
    booking_id = booking["id"]
    assert booking["status"] == "confirmed"
    assert booking["code"].startswith("BK-")
    assert booking["userId"] == DEFAULT_USER_ID

    # ── Step 5: Verify booking in list ───────────────────────────────
    r = http.get(f"{GATEWAY_URL}/api/v1/bookings", headers=headers)
    assert r.status_code == 200
    data = r.json()
    bookings = data if isinstance(data, list) else data.get("data", data.get("items", []))
    booking_ids = [b["id"] for b in bookings]
    assert booking_id in booking_ids, "Booking should appear in user's booking list"

    # ── Step 6: Clean up cart ────────────────────────────────────────
    http.delete(f"{GATEWAY_URL}/api/v1/cart", headers=headers)
