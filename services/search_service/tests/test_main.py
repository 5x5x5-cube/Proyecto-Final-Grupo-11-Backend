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


def test_health_check(mock_redis):
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "search-service"


def test_root(mock_redis):
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "search-service"
    assert "endpoints" in response.json()


def test_search_hotels_endpoint_exists(mock_redis):
    """Test that search hotels endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/search/hotels" in routes
