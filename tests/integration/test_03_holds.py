"""Test 3: Hold lifecycle — create, check, get, release (direct inventory access)."""

from datetime import date, timedelta

from conftest import (
    ALT_USER_ID,
    DEFAULT_USER_ID,
    INVENTORY_URL,
    ROOM_DELUXE_CARIBE_ID,
    ROOM_STANDARD_CARIBE_ID,
    user_headers,
)

CHECK_IN = (date.today() + timedelta(days=20)).isoformat()
CHECK_OUT = (date.today() + timedelta(days=22)).isoformat()


def test_create_hold(http):
    r = http.post(
        f"{INVENTORY_URL}/holds",
        json={"roomId": ROOM_DELUXE_CARIBE_ID, "checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(),
    )
    assert r.status_code == 201, r.text
    hold = r.json()
    assert hold["room_id"] == ROOM_DELUXE_CARIBE_ID
    assert hold["user_id"] == DEFAULT_USER_ID
    assert hold["status"] == "active"
    assert hold["check_in"] == CHECK_IN
    assert hold["check_out"] == CHECK_OUT
    assert hold["price_per_night"] is not None

    # Store for subsequent tests
    test_create_hold.hold_id = hold["id"]


def test_get_hold(http):
    hold_id = test_create_hold.hold_id
    r = http.get(f"{INVENTORY_URL}/holds/{hold_id}", headers=user_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == hold_id
    assert data["ttl_seconds"] > 0  # TTL still active


def test_check_hold_same_user(http):
    r = http.get(
        f"{INVENTORY_URL}/holds/check/{ROOM_DELUXE_CARIBE_ID}",
        params={"checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["held"] is True
    assert data["same_user"] is True


def test_check_hold_different_user(http):
    r = http.get(
        f"{INVENTORY_URL}/holds/check/{ROOM_DELUXE_CARIBE_ID}",
        params={"checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(ALT_USER_ID),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["held"] is True
    assert data["same_user"] is False


def test_check_no_hold_on_different_room(http):
    r = http.get(
        f"{INVENTORY_URL}/holds/check/{ROOM_STANDARD_CARIBE_ID}",
        params={"checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["held"] is False


def test_release_hold(http):
    hold_id = test_create_hold.hold_id
    r = http.delete(f"{INVENTORY_URL}/holds/{hold_id}", headers=user_headers())
    assert r.status_code == 204


def test_hold_released_check(http):
    r = http.get(
        f"{INVENTORY_URL}/holds/check/{ROOM_DELUXE_CARIBE_ID}",
        params={"checkIn": CHECK_IN, "checkOut": CHECK_OUT},
        headers=user_headers(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["held"] is False
