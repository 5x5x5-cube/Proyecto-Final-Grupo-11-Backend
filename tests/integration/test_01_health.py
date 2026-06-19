"""Test 1: Health checks — verify all services are up and responding."""

import pytest
from conftest import BOOKING_URL, CART_URL, GATEWAY_URL, INVENTORY_URL, SEARCH_URL

SERVICES = {
    "gateway": GATEWAY_URL,
    "inventory": INVENTORY_URL,
    "booking": BOOKING_URL,
    "cart": CART_URL,
    "search": SEARCH_URL,
}


@pytest.mark.parametrize("name,base_url", SERVICES.items())
def test_health_endpoint(http, name, base_url):
    r = http.get(f"{base_url}/health")
    assert r.status_code == 200, f"{name} health check failed: {r.text}"
    data = r.json()
    assert data.get("status") == "healthy" or "status" in data


@pytest.mark.parametrize("name,base_url", SERVICES.items())
def test_root_endpoint(http, name, base_url):
    r = http.get(f"{base_url}/")
    assert r.status_code == 200, f"{name} root endpoint failed: {r.text}"
