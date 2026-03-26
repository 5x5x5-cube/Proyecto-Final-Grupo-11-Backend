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


@pytest.mark.asyncio
async def test_search_endpoint_exists(mock_redis):
    """Test that search endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/search" in routes


@pytest.mark.asyncio  
async def test_accommodations_endpoint_exists(mock_redis):
    """Test that accommodations endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/accommodations/{accommodation_id}" in routes
