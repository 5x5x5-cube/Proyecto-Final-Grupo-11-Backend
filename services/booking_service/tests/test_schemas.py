"""Tests for Pydantic schema validation."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas import BookingResponse, CreateBookingRequest, PriceBreakdown

ROOM_ID = uuid.uuid4()
HOTEL_ID = uuid.uuid4()
HOLD_ID = uuid.uuid4()


def _base_request_kwargs(**overrides):
    """Return a dict of valid CreateBookingRequest keyword arguments."""
    defaults = dict(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        hold_id=HOLD_ID,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 5),
        guests=2,
        base_price=Decimal("500000"),
        tax_amount=Decimal("95000"),
        service_fee=Decimal("0"),
        total_price=Decimal("595000"),
    )
    defaults.update(overrides)
    return defaults


def test_create_booking_request_camel_case():
    """CreateBookingRequest accepts camelCase aliases."""
    data = {
        "roomId": str(ROOM_ID),
        "hotelId": str(HOTEL_ID),
        "holdId": str(HOLD_ID),
        "checkIn": "2026-04-01",
        "checkOut": "2026-04-05",
        "guests": 2,
        "basePrice": 500000,
        "taxAmount": 95000,
        "serviceFee": 0,
        "totalPrice": 595000,
    }
    req = CreateBookingRequest(**data)
    assert isinstance(req.room_id, uuid.UUID)
    assert isinstance(req.check_in, date)
    assert req.guests == 2
    assert req.hold_id == uuid.UUID(data["holdId"])
    assert req.base_price == Decimal("500000")
    assert req.total_price == Decimal("595000")


def test_create_booking_request_snake_case():
    """CreateBookingRequest accepts snake_case field names."""
    req = CreateBookingRequest(**_base_request_kwargs())
    assert req.guests == 2
    assert req.hotel_id == HOTEL_ID
    assert req.hold_id == HOLD_ID


def test_create_booking_request_invalid_guests_zero():
    """guests=0 should raise a ValidationError."""
    with pytest.raises(ValidationError):
        CreateBookingRequest(**_base_request_kwargs(guests=0))


def test_create_booking_request_invalid_guests_max():
    """guests=11 exceeds the maximum of 10 and should raise a ValidationError."""
    with pytest.raises(ValidationError):
        CreateBookingRequest(**_base_request_kwargs(guests=11))


def test_create_booking_request_service_fee_defaults_to_zero():
    """serviceFee is optional and defaults to 0."""
    kwargs = _base_request_kwargs()
    del kwargs["service_fee"]
    req = CreateBookingRequest(**kwargs)
    assert req.service_fee == Decimal("0")


def test_create_booking_request_requires_hold_id():
    """holdId is required — omitting it raises a ValidationError."""
    kwargs = _base_request_kwargs()
    del kwargs["hold_id"]
    with pytest.raises(ValidationError):
        CreateBookingRequest(**kwargs)


def test_create_booking_request_requires_base_price():
    """basePrice is required — omitting it raises a ValidationError."""
    kwargs = _base_request_kwargs()
    del kwargs["base_price"]
    with pytest.raises(ValidationError):
        CreateBookingRequest(**kwargs)


def test_price_breakdown():
    """PriceBreakdown accepts camelCase and exposes snake_case attributes."""
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
    assert pb.nights == 3


def test_booking_response():
    """BookingResponse can be constructed and exposes the expected fields."""
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
        status="confirmed",
        totalPrice=595000,
        currency="COP",
        priceBreakdown=None,
        holdExpiresAt=None,
        createdAt=now,
    )
    assert resp.status == "confirmed"
    assert resp.code == "BK-ABCD1234"
    assert resp.hold_id is not None
