"""Edge-case tests for the simplified booking_service."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.schemas import CreateBookingRequest
from app.services.booking_service import create_booking

# ---------------------------------------------------------------------------
# Fixed UUIDs for predictability
# ---------------------------------------------------------------------------

ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")


def _make_request(
    check_in: date | None = None,
    check_out: date | None = None,
    guests: int = 2,
    base_price: Decimal = Decimal("500000"),
    tax_amount: Decimal = Decimal("95000"),
    total_price: Decimal = Decimal("595000"),
) -> CreateBookingRequest:
    ci = check_in or date.today() + timedelta(days=1)
    co = check_out or date.today() + timedelta(days=3)
    return CreateBookingRequest(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        hold_id=HOLD_ID,
        check_in=ci,
        check_out=co,
        guests=guests,
        base_price=base_price,
        tax_amount=tax_amount,
        service_fee=Decimal("0"),
        total_price=total_price,
    )


def _make_fake_db_refresh():
    async def fake_refresh(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.code is None:
            obj.code = "BK-TEST1234"
        if obj.currency is None:
            obj.currency = "COP"
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if obj.updated_at is None:
            obj.updated_at = datetime.now(timezone.utc)

    return fake_refresh


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


async def test_same_day_checkout_zero_price():
    """A booking where base_price=0 and total_price=0 is inserted without error."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = _make_request(
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=1),
        base_price=Decimal("0"),
        tax_amount=Decimal("0"),
        total_price=Decimal("0"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.total_price == 0.0
    assert result.status == "pending"
    db.add.assert_called_once()
    db.commit.assert_called_once()


async def test_multiple_guests_booking():
    """A booking for the maximum 10 guests is inserted successfully."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    result = await create_booking(db=db, user_id=USER_ID, request=_make_request(guests=10))

    assert result.guests == 10
    assert result.status == "pending"


async def test_single_guest_booking():
    """A booking for 1 guest is inserted successfully."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    result = await create_booking(db=db, user_id=USER_ID, request=_make_request(guests=1))

    assert result.guests == 1
    assert result.status == "pending"


async def test_db_commit_failure_propagates():
    """A DB failure during commit propagates to the caller unchanged."""
    db = AsyncMock()
    db.commit.side_effect = RuntimeError("connection lost")

    with pytest.raises(RuntimeError, match="connection lost"):
        await create_booking(db=db, user_id=USER_ID, request=_make_request())


async def test_large_price_values():
    """Large price values (e.g., luxury suite) are stored without truncation."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = _make_request(
        base_price=Decimal("99999999.99"),
        tax_amount=Decimal("18999999.99"),
        total_price=Decimal("118999999.98"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.total_price == pytest.approx(118999999.98)
    assert result.status == "pending"


async def test_hold_id_is_persisted():
    """The holdId from the request is stored on the created booking."""
    custom_hold_id = uuid.uuid4()
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = CreateBookingRequest(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        hold_id=custom_hold_id,
        check_in=date.today() + timedelta(days=5),
        check_out=date.today() + timedelta(days=7),
        guests=2,
        base_price=Decimal("400000"),
        tax_amount=Decimal("76000"),
        service_fee=Decimal("0"),
        total_price=Decimal("476000"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.hold_id == custom_hold_id
