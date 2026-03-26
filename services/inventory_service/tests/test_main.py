import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "inventory-service"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "inventory-service"
    assert "endpoints" in response.json()


@pytest.mark.asyncio
async def test_webhooks_endpoint_exists():
    """Test that webhook endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/webhooks/accommodation" in routes


@pytest.mark.asyncio
async def test_accommodations_endpoint_exists():
    """Test that accommodations endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/accommodations" in routes
