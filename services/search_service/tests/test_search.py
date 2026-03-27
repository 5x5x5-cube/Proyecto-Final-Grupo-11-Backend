from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def mock_redis():
    with patch("app.redis_client.redis.from_url") as mock:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_search_service():
    with patch("app.routes.search.search_service") as mock:
        mock.search.return_value = {
            "results": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
            "filters_applied": {},
            "sort": {"by": "popularity", "order": "desc"},
        }
        yield mock


def test_search_hotels_endpoint_exists(mock_redis, mock_search_service):
    """Test search hotels endpoint returns expected structure"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {},
    }
    client = TestClient(app)
    response = client.get("/search/hotels")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data


def test_search_with_city_filter(mock_redis, mock_search_service):
    """Test search with city parameter"""
    mock_search_service.search_hotels.return_value = {
        "results": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "total_pages": 0,
        "filters": {"city": "Madrid"},
    }
    client = TestClient(app)
    response = client.get("/search/hotels?city=Madrid")
    assert response.status_code == 200


def test_invalid_dates_validation(mock_redis):
    """Test that invalid dates return 400"""
    client = TestClient(app)
    response = client.get("/search/hotels?check_in=2024-01-10&check_out=2024-01-05")
    assert response.status_code == 400
