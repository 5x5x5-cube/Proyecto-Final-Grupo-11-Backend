import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_accommodation_service():
    with patch('app.routes.webhooks.AccommodationService') as mock:
        mock.get_accommodation_by_external_id = AsyncMock(return_value=None)
        mock.create_accommodation = AsyncMock()
        mock.create_accommodation.return_value.id = "test-id-123"
        mock.create_accommodation.return_value.external_id = "test-external-123"
        yield mock


@pytest.fixture
def sample_accommodation_data():
    return {
        "external_id": "test-001",
        "provider": "test-provider",
        "title": "Test Accommodation",
        "description": "Test description",
        "accommodation_type": "apartment",
        "location": {
            "city": "Madrid",
            "country": "Spain",
            "address": "Test Address 123",
            "postal_code": "28013",
            "coordinates": {"lat": 40.4168, "lon": -3.7038}
        },
        "pricing": {
            "base_price": 100.0,
            "currency": "USD",
            "cleaning_fee": 20.0,
            "service_fee": 10.0
        },
        "capacity": {
            "max_guests": 4,
            "bedrooms": 2,
            "beds": 2,
            "bathrooms": 1.0
        },
        "rating": {
            "average": 4.5,
            "count": 100
        },
        "popularity": {
            "views_count": 1000,
            "bookings_count": 50,
            "favorites_count": 75
        },
        "amenities": ["wifi", "kitchen"],
        "images": [
            {"url": "https://example.com/image.jpg", "is_primary": True, "order": 0}
        ],
        "availability": {
            "is_available": True,
            "minimum_nights": 1
        },
        "policies": {
            "cancellation_policy": "flexible",
            "check_in_time": "15:00",
            "check_out_time": "11:00"
        }
    }


def test_webhook_endpoint_registered():
    """Test that webhook endpoint is registered"""
    routes = [route.path for route in app.routes]
    assert "/webhooks/accommodation" in routes
