import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Cart


@pytest.fixture
def sample_user_id():
    return uuid.UUID("c1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_room_id():
    return uuid.UUID("b1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_hotel_id():
    return uuid.UUID("a1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_hold_id():
    return uuid.UUID("d1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_cart(sample_user_id, sample_room_id, sample_hotel_id, sample_hold_id):
    return Cart(
        id=uuid.uuid4(),
        user_id=sample_user_id,
        room_id=sample_room_id,
        hotel_id=sample_hotel_id,
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=3),
        guests=2,
        hold_id=sample_hold_id,
        hold_expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        price_per_night=250000,
        tax_rate=0.19,
        room_type="Deluxe",
        hotel_name="Hotel Test",
        room_name="Deluxe Room",
        location="Bogota, Colombia",
        rating=4.5,
        review_count=120,
        room_features="Ocean view, King bed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_hold_response(sample_hold_id, sample_room_id, sample_user_id):
    return {
        "id": str(sample_hold_id),
        "room_id": str(sample_room_id),
        "user_id": str(sample_user_id),
        "check_in": (date.today() + timedelta(days=1)).isoformat(),
        "check_out": (date.today() + timedelta(days=3)).isoformat(),
        "status": "active",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "price_per_night": 250000,
        "tax_rate": 0.19,
        "room_type": "Deluxe",
    }


@pytest.fixture
def mock_room_response(sample_room_id, sample_hotel_id):
    return {
        "id": str(sample_room_id),
        "hotel_id": str(sample_hotel_id),
        "room_type": "Deluxe",
        "room_number": "101",
        "capacity": 2,
        "price_per_night": 250000,
        "tax_rate": 0.19,
        "description": "Ocean view, King bed",
        "amenities": None,
        "total_quantity": 5,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def mock_hotel_response(sample_hotel_id):
    return {
        "id": str(sample_hotel_id),
        "name": "Hotel Test",
        "description": "A great hotel",
        "city": "Bogota",
        "country": "Colombia",
        "rating": 4.5,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
