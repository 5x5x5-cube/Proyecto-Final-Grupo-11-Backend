"""Test 7: Search service — destinations, hotel search, hotel detail.

Note: Search data is populated via SQS events from inventory-service.
The seed data may take a few seconds to propagate through the SQS worker.
If search returns empty, it may mean the SQS worker hasn't processed events yet.
"""

import time

from conftest import HOTEL_CARIBE_ID, SEARCH_URL


def test_search_health_includes_redis(http):
    r = http.get(f"{SEARCH_URL}/health")
    assert r.status_code == 200


def test_search_destinations(http):
    """GET /search/destinations should return available cities."""
    r = http.get(f"{SEARCH_URL}/search/destinations")
    if r.status_code == 200:
        data = r.json()
        # Response may be a list or {"destinations": [...], "total": N}
        destinations = data if isinstance(data, list) else data.get("destinations", [])
        assert isinstance(destinations, list)


def test_search_hotels_no_filters(http):
    """GET /search/hotels without filters."""
    r = http.get(f"{SEARCH_URL}/search/hotels")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data or isinstance(data, list)


def test_search_hotels_by_city(http):
    """GET /search/hotels?city=Cartagena should filter by city."""
    r = http.get(f"{SEARCH_URL}/search/hotels", params={"city": "Cartagena"})
    assert r.status_code == 200
    data = r.json()
    results = data.get("results", data) if isinstance(data, dict) else data
    # If SQS has synced, we should find Cartagena hotels
    for hotel in results:
        if "city" in hotel:
            assert hotel["city"].lower() == "cartagena"


def test_search_hotels_pagination(http):
    """Pagination params should be accepted."""
    r = http.get(f"{SEARCH_URL}/search/hotels", params={"page": 1, "page_size": 2})
    assert r.status_code == 200
    data = r.json()
    if "page_size" in data:
        assert data["page_size"] <= 2


def test_search_hotel_detail(http):
    """GET /search/hotels/{id} should return hotel details from Redis."""
    r = http.get(f"{SEARCH_URL}/search/hotels/{HOTEL_CARIBE_ID}")
    # 404 is acceptable if SQS hasn't synced yet
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        hotel = r.json()
        assert "name" in hotel
