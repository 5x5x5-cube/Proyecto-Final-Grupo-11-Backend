"""Test 4: Cart service — upsert, get, delete (direct access)."""

from datetime import date, timedelta

from conftest import CART_URL, HOTEL_CARIBE_ID, ROOM_STANDARD_CARIBE_ID, user_headers

CHECK_IN = (date.today() + timedelta(days=25)).isoformat()
CHECK_OUT = (date.today() + timedelta(days=27)).isoformat()


def test_cart_cleanup_before_tests(http):
    """Ensure no leftover cart from previous runs."""
    http.delete(f"{CART_URL}/api/v1/cart", headers=user_headers())
    r = http.get(f"{CART_URL}/api/v1/cart", headers=user_headers())
    assert r.status_code in (404, 410), f"Expected 404/410, got {r.status_code}: {r.text}"


def test_upsert_cart(http):
    r = http.put(
        f"{CART_URL}/api/v1/cart",
        json={
            "roomId": ROOM_STANDARD_CARIBE_ID,
            "hotelId": HOTEL_CARIBE_ID,
            "checkIn": CHECK_IN,
            "checkOut": CHECK_OUT,
            "guests": 2,
        },
        headers=user_headers(),
    )
    assert r.status_code in (200, 201), f"Upsert failed: {r.text}"
    cart = r.json()
    assert cart["roomId"] == ROOM_STANDARD_CARIBE_ID
    assert cart["hotelId"] == HOTEL_CARIBE_ID
    assert cart["guests"] == 2
    assert cart["holdId"] is not None

    test_upsert_cart.hold_id = cart["holdId"]


def test_get_cart(http):
    r = http.get(f"{CART_URL}/api/v1/cart", headers=user_headers())
    assert r.status_code == 200
    cart = r.json()
    assert cart["roomId"] == ROOM_STANDARD_CARIBE_ID
    assert cart["checkIn"] == CHECK_IN
    assert cart["checkOut"] == CHECK_OUT
    assert cart.get("priceBreakdown") is not None


def test_upsert_cart_replaces_previous(http):
    """Upserting with a different room should replace the cart and release the old hold."""
    from conftest import HOTEL_BOGOTA_ID, ROOM_STANDARD_BOGOTA_ID

    new_check_in = (date.today() + timedelta(days=30)).isoformat()
    new_check_out = (date.today() + timedelta(days=32)).isoformat()

    r = http.put(
        f"{CART_URL}/api/v1/cart",
        json={
            "roomId": ROOM_STANDARD_BOGOTA_ID,
            "hotelId": HOTEL_BOGOTA_ID,
            "checkIn": new_check_in,
            "checkOut": new_check_out,
            "guests": 1,
        },
        headers=user_headers(),
    )
    assert r.status_code in (200, 201), f"Upsert replace failed: {r.text}"
    cart = r.json()
    assert cart["roomId"] == ROOM_STANDARD_BOGOTA_ID
    assert cart["holdId"] != test_upsert_cart.hold_id  # New hold created


def test_delete_cart(http):
    r = http.delete(f"{CART_URL}/api/v1/cart", headers=user_headers())
    assert r.status_code in (200, 204), f"Delete cart failed: {r.text}"


def test_cart_gone_after_delete(http):
    r = http.get(f"{CART_URL}/api/v1/cart", headers=user_headers())
    assert r.status_code in (404, 410)
