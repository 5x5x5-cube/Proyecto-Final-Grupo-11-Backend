import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Availability, Base, Hold, Hotel, Room


@pytest.fixture
def sample_hotel_id():
    return uuid.UUID("a1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_room_id():
    return uuid.UUID("b1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_user_id():
    return uuid.UUID("c1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_hotel(sample_hotel_id):
    return Hotel(
        id=sample_hotel_id,
        name="Test Hotel",
        description="A test hotel",
        city="Bogota",
        country="Colombia",
        rating=4.5,
    )


@pytest.fixture
def sample_room(sample_room_id, sample_hotel_id):
    return Room(
        id=sample_room_id,
        hotel_id=sample_hotel_id,
        room_type="Standard",
        room_number="101",
        capacity=2,
        price_per_night=250000,
        tax_rate=0.19,
        total_quantity=1,
    )


@pytest.fixture
def sample_availability(sample_room_id):
    tomorrow = date.today() + timedelta(days=1)
    return Availability(
        id=uuid.uuid4(),
        room_id=sample_room_id,
        date=tomorrow,
        total_quantity=1,
        available_quantity=1,
    )


@pytest.fixture
def sample_hold(sample_room_id, sample_user_id):
    return Hold(
        id=uuid.uuid4(),
        room_id=sample_room_id,
        user_id=sample_user_id,
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=3),
        status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
