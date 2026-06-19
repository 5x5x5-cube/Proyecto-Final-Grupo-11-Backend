"""Test 6: Gateway — verify proxy routing to backend services."""

from datetime import date, timedelta

from conftest import DEFAULT_USER_ID, GATEWAY_URL, ROOM_STANDARD_CARIBE_ID, user_headers


def test_gateway_proxies_to_booking(http):
    """GET /api/v1/bookings through gateway should reach booking-service."""
    r = http.get(f"{GATEWAY_URL}/api/v1/bookings", headers=user_headers())
    assert r.status_code == 200, f"Gateway -> booking failed: {r.text}"


def test_gateway_proxies_to_search(http):
    """GET /api/v1/search/destinations through gateway should reach search-service."""
    r = http.get(f"{GATEWAY_URL}/api/v1/search/destinations")
    # search service may return 200 or data depending on redis state
    assert r.status_code in (200, 404), f"Gateway -> search failed: {r.text}"


def test_gateway_proxies_to_cart(http):
    """GET /api/v1/cart through gateway should reach cart-service."""
    r = http.get(f"{GATEWAY_URL}/api/v1/cart", headers=user_headers())
    # 404 or 410 is fine — means cart-service responded (no cart exists)
    assert r.status_code in (200, 404, 410), f"Gateway -> cart failed: {r.text}"


def test_gateway_injects_user_id(http):
    """Gateway should inject DEFAULT_USER_ID when no X-User-Id is provided."""
    r = http.get(f"{GATEWAY_URL}/api/v1/bookings")
    # Should succeed (gateway injects default user) rather than 401
    assert r.status_code == 200, f"Gateway user injection failed: {r.text}"


def test_gateway_unknown_service_returns_501(http):
    """Routing to an unconfigured service should return 501."""
    r = http.get(f"{GATEWAY_URL}/api/v1/auth/login")
    assert r.status_code == 501, f"Expected 501 for unconfigured service, got {r.status_code}"


def test_gateway_full_flow_cart_upsert(http):
    """PUT /api/v1/cart through gateway should create a cart + hold."""
    from conftest import HOTEL_CARIBE_ID

    check_in = (date.today() + timedelta(days=40)).isoformat()
    check_out = (date.today() + timedelta(days=42)).isoformat()

    r = http.put(
        f"{GATEWAY_URL}/api/v1/cart",
        json={
            "roomId": ROOM_STANDARD_CARIBE_ID,
            "hotelId": HOTEL_CARIBE_ID,
            "checkIn": check_in,
            "checkOut": check_out,
            "guests": 2,
        },
        headers=user_headers(),
    )
    assert r.status_code in (200, 201), f"Gateway cart upsert failed: {r.text}"
    cart = r.json()
    assert cart["roomId"] == ROOM_STANDARD_CARIBE_ID

    # Clean up
    http.delete(f"{GATEWAY_URL}/api/v1/cart", headers=user_headers())
