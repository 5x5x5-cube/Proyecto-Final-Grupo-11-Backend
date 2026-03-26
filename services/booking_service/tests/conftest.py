import uuid
from datetime import date, datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import Booking


def sample_room_id():
    return uuid.UUID("b1000000-0000-0000-0000-000000000001")


def sample_hotel_id():
    return uuid.UUID("a1000000-0000-0000-0000-000000000001")


def sample_user_id():
    return uuid.UUID("c1000000-0000-0000-0000-000000000001")


def sample_hold_id():
    return uuid.UUID("d1000000-0000-0000-0000-000000000001")


def make_sample_booking(
    user_id: uuid.UUID | None = None,
    hotel_id: uuid.UUID | None = None,
    room_id: uuid.UUID | None = None,
    hold_id: uuid.UUID | None = None,
    status: str = "confirmed",
) -> Booking:
    return Booking(
        id=uuid.uuid4(),
        code="BK-TEST1234",
        user_id=user_id or sample_user_id(),
        hotel_id=hotel_id or sample_hotel_id(),
        room_id=room_id or sample_room_id(),
        hold_id=hold_id or sample_hold_id(),
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=3),
        guests=2,
        status=status,
        base_price=500000,
        tax_amount=95000,
        service_fee=0,
        total_price=595000,
        currency="COP",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
