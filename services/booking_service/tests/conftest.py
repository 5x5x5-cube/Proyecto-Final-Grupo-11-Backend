import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Booking


@pytest.fixture
def sample_room_id():
    return uuid.UUID("b1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_hotel_id():
    return uuid.UUID("a1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_user_id():
    return uuid.UUID("c1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_hold_id():
    return uuid.UUID("d1000000-0000-0000-0000-000000000001")


@pytest.fixture
def sample_booking(sample_room_id, sample_hotel_id, sample_user_id, sample_hold_id):
    return Booking(
        id=uuid.uuid4(),
        code="BK-TEST1234",
        user_id=sample_user_id,
        hotel_id=sample_hotel_id,
        room_id=sample_room_id,
        hold_id=sample_hold_id,
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=3),
        guests=2,
        status="pending",
        base_price=500000,
        tax_amount=95000,
        service_fee=0,
        total_price=595000,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def async_client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")
