import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app


@pytest.fixture
def mock_redis():
    with patch('app.redis_client.redis.from_url') as mock:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_search_service():
    with patch('app.routes.search.search_service') as mock:
        mock.search.return_value = {
            "results": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
            "filters_applied": {},
            "sort": {"by": "popularity", "order": "desc"}
        }
        mock.get_suggestions.return_value = {
            "cities": [],
            "accommodations": []
        }
        yield mock


def test_search_endpoint_registered(mock_redis):
    """Test that search endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/search" in routes


def test_search_endpoint_returns_results(mock_redis, mock_search_service):
    """Test search endpoint returns expected structure"""
    client = TestClient(app)
    response = client.get("/search")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data


def test_search_with_filters(mock_redis, mock_search_service):
    """Test search with query parameters"""
    client = TestClient(app)
    response = client.get("/search?city=Madrid&min_price=50&max_price=200")
    assert response.status_code == 200


def test_suggestions_endpoint(mock_redis, mock_search_service):
    """Test suggestions endpoint"""
    client = TestClient(app)
    response = client.get("/search/suggestions?q=Mad")
    assert response.status_code == 200
    data = response.json()
    assert "cities" in data
    assert "accommodations" in data
