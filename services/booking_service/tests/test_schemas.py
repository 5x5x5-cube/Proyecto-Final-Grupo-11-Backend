import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas import BookingResponse, CreateBookingRequest, PriceBreakdown


def test_create_booking_request_camel_case():
    data = {
        "roomId": str(uuid.uuid4()),
        "hotelId": str(uuid.uuid4()),
        "checkIn": "2026-04-01",
        "checkOut": "2026-04-05",
        "guests": 2,
        "userId": str(uuid.uuid4()),
    }
    req = CreateBookingRequest(**data)
    assert isinstance(req.room_id, uuid.UUID)
    assert isinstance(req.check_in, date)
    assert req.guests == 2


def test_create_booking_request_snake_case():
    req = CreateBookingRequest(
        room_id=uuid.uuid4(),
        hotel_id=uuid.uuid4(),
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 5),
        guests=2,
        user_id=uuid.uuid4(),
    )
    assert req.guests == 2


def test_create_booking_request_invalid_guests():
    with pytest.raises(ValidationError):
        CreateBookingRequest(
            room_id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 5),
            guests=0,
            user_id=uuid.uuid4(),
        )


def test_create_booking_request_max_guests():
    with pytest.raises(ValidationError):
        CreateBookingRequest(
            room_id=uuid.uuid4(),
            hotel_id=uuid.uuid4(),
            check_in=date(2026, 4, 1),
            check_out=date(2026, 4, 5),
            guests=11,
            user_id=uuid.uuid4(),
        )


def test_price_breakdown():
    pb = PriceBreakdown(
        pricePerNight=250000,
        nights=3,
        basePrice=750000,
        vat=142500,
        serviceFee=0,
        totalPrice=892500,
        currency="COP",
    )
    assert pb.price_per_night == 250000
    assert pb.total_price == 892500


def test_booking_response():
    now = datetime.now(timezone.utc)
    resp = BookingResponse(
        id=uuid.uuid4(),
        code="BK-ABCD1234",
        userId=uuid.uuid4(),
        hotelId=uuid.uuid4(),
        roomId=uuid.uuid4(),
        holdId=uuid.uuid4(),
        checkIn=date(2026, 4, 1),
        checkOut=date(2026, 4, 5),
        guests=2,
        status="pending",
        totalPrice=892500,
        currency="COP",
        priceBreakdown=None,
        holdExpiresAt=now,
        createdAt=now,
    )
    assert resp.status == "pending"
    assert resp.code == "BK-ABCD1234"
