"""Tests for the simplified create_booking service function."""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

from app.schemas import CreateBookingRequest
from app.services.booking_service import create_booking

# ---------------------------------------------------------------------------
# Fixed UUIDs for predictability
# ---------------------------------------------------------------------------

ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")

CHECK_IN = date.today() + timedelta(days=1)
CHECK_OUT = date.today() + timedelta(days=3)


def _make_request(
    check_in: date = CHECK_IN,
    check_out: date = CHECK_OUT,
    guests: int = 2,
    base_price: Decimal = Decimal("500000"),
    tax_amount: Decimal = Decimal("95000"),
    service_fee: Decimal = Decimal("0"),
    total_price: Decimal = Decimal("595000"),
) -> CreateBookingRequest:
    return CreateBookingRequest(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        hold_id=HOLD_ID,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        base_price=base_price,
        tax_amount=tax_amount,
        service_fee=service_fee,
        total_price=total_price,
    )


def _make_fake_db_refresh():
    """Return a side_effect function that populates auto-generated ORM fields."""

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


async def test_create_booking_success():
    """create_booking inserts a pending booking and returns a BookingResponse."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = _make_request()
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.status == "pending"
    assert result.guests == 2
    assert result.total_price == 595000.0
    assert result.hold_id == HOLD_ID
    assert result.user_id == USER_ID
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()


async def test_create_booking_sets_pending_status():
    """create_booking always sets status to 'pending'."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    result = await create_booking(db=db, user_id=USER_ID, request=_make_request())

    assert result.status == "pending"


async def test_create_booking_stores_correct_prices():
    """create_booking persists all price fields from the request."""
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = _make_request(
        base_price=Decimal("750000"),
        tax_amount=Decimal("142500"),
        service_fee=Decimal("10000"),
        total_price=Decimal("902500"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.total_price == 902500.0


async def test_create_booking_db_failure_propagates():
    """If the DB commit fails, the exception propagates to the caller."""
    db = AsyncMock()
    db.commit.side_effect = Exception("DB connection lost")

    import pytest

    with pytest.raises(Exception, match="DB connection lost"):
        await create_booking(db=db, user_id=USER_ID, request=_make_request())


async def test_create_booking_stores_hold_id():
    """create_booking stores the holdId from the request."""
    custom_hold_id = uuid.uuid4()
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    request = CreateBookingRequest(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        hold_id=custom_hold_id,
        check_in=CHECK_IN,
        check_out=CHECK_OUT,
        guests=1,
        base_price=Decimal("250000"),
        tax_amount=Decimal("47500"),
        service_fee=Decimal("0"),
        total_price=Decimal("297500"),
    )
    result = await create_booking(db=db, user_id=USER_ID, request=request)

    assert result.hold_id == custom_hold_id


async def test_create_booking_uses_user_id_from_argument():
    """create_booking uses the user_id argument, not one from the request body."""
    other_user_id = uuid.uuid4()
    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())

    result = await create_booking(db=db, user_id=other_user_id, request=_make_request())

    assert result.user_id == other_user_id
