import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import InventoryServiceError
from app.redis_lock import LockAcquisitionError
from app.schemas import CreateBookingRequest
from app.services.booking_service import create_booking

# ---------------------------------------------------------------------------
# Fixed UUIDs for predictability
# ---------------------------------------------------------------------------

ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
HOLD_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")

# ---------------------------------------------------------------------------
# Shared helpers — mirrors the patterns in test_booking_creation.py
# ---------------------------------------------------------------------------


def _make_request(check_in: date, check_out: date, guests: int = 2) -> CreateBookingRequest:
    return CreateBookingRequest(
        room_id=ROOM_ID,
        hotel_id=HOTEL_ID,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        user_id=USER_ID,
    )


def _make_hold_response(
    price_per_night: float = 250000.0,
    tax_rate: float = 0.19,
    hold_id: str | None = None,
    expires_at: str | None = None,
) -> dict:
    hid = hold_id or str(HOLD_ID)
    return {
        "id": hid,
        "room_id": str(ROOM_ID),
        "user_id": str(USER_ID),
        "check_in": (date.today() + timedelta(days=1)).isoformat(),
        "check_out": (date.today() + timedelta(days=3)).isoformat(),
        "status": "active",
        "expires_at": expires_at,
        "price_per_night": price_per_night,
        "tax_rate": tax_rate,
        "room_type": "Standard",
    }


def _make_fake_db_refresh():
    """Return a side_effect function that populates auto-generated ORM fields."""

    async def fake_refresh(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.code is None:
            obj.code = "BK-TEST1234"
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if obj.updated_at is None:
            obj.updated_at = datetime.now(timezone.utc)

    return fake_refresh


def _make_lock_mock() -> AsyncMock:
    """Return a mock that behaves as an async context manager lock (acquired)."""
    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    return mock_lock


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_same_day_checkout_zero_nights(mock_lock_factory, mock_inventory):
    """Same-day checkout (checkIn == checkOut) produces 0 nights and total_price == 0."""
    same_day = date.today() + timedelta(days=1)

    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    mock_inventory.create_hold = AsyncMock(
        return_value=_make_hold_response(
            price_per_night=250000.0,
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        )
    )
    mock_lock_factory.return_value = _make_lock_mock()

    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())
    redis = AsyncMock()
    request = _make_request(check_in=same_day, check_out=same_day)

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.price_breakdown is not None
    assert result.price_breakdown.nights == 0
    assert result.price_breakdown.base_price == 0.0
    assert result.total_price == 0.0
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_lock_acquisition_failure_raises_503(mock_lock_factory, mock_inventory):
    """When the Redis lock cannot be acquired, create_booking raises InventoryServiceError(503)."""
    mock_inventory.check_hold = AsyncMock(return_value={"held": False})

    # Lock raises LockAcquisitionError on __aenter__
    failing_lock = AsyncMock()
    failing_lock.__aenter__ = AsyncMock(side_effect=LockAcquisitionError("lock:booking:test"))
    failing_lock.__aexit__ = AsyncMock(return_value=False)
    mock_lock_factory.return_value = failing_lock

    db = AsyncMock()
    redis = AsyncMock()
    check_in = date.today() + timedelta(days=1)
    check_out = date.today() + timedelta(days=3)
    request = _make_request(check_in=check_in, check_out=check_out)

    with pytest.raises(InventoryServiceError) as exc_info:
        await create_booking(db=db, redis=redis, request=request)

    assert exc_info.value.status_code == 503
    assert "busy" in str(exc_info.value).lower()


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_hold_response_missing_expires_at(mock_lock_factory, mock_inventory):
    """Hold response with expires_at=None results in a booking with holdExpiresAt=None."""
    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    # expires_at is None — omitted from the hold response
    mock_inventory.create_hold = AsyncMock(return_value=_make_hold_response(expires_at=None))
    mock_lock_factory.return_value = _make_lock_mock()

    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())
    redis = AsyncMock()
    check_in = date.today() + timedelta(days=1)
    check_out = date.today() + timedelta(days=3)
    request = _make_request(check_in=check_in, check_out=check_out)

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.hold_expires_at is None
    assert result.status == "pending"
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_same_user_re_hold_proceeds_normally(mock_lock_factory, mock_inventory):
    """When hold_check returns held=True and same_user=True, booking proceeds without raising."""
    mock_inventory.check_hold = AsyncMock(
        return_value={
            "held": True,
            "same_user": True,
            "holder_id": str(USER_ID),
            "hold_id": str(HOLD_ID),
        }
    )
    mock_inventory.create_hold = AsyncMock(
        return_value=_make_hold_response(
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        )
    )
    mock_lock_factory.return_value = _make_lock_mock()

    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())
    redis = AsyncMock()
    check_in = date.today() + timedelta(days=1)
    check_out = date.today() + timedelta(days=3)
    request = _make_request(check_in=check_in, check_out=check_out)

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.status == "pending"
    mock_inventory.create_hold.assert_called_once()
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_price_calculation_accuracy(mock_lock_factory, mock_inventory):
    """3 nights at 250000 COP with 19% tax → base=750000, vat=142500, total=892500."""
    check_in = date.today() + timedelta(days=1)
    check_out = check_in + timedelta(days=3)  # exactly 3 nights

    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    mock_inventory.create_hold = AsyncMock(
        return_value=_make_hold_response(
            price_per_night=250000.0,
            tax_rate=0.19,
            expires_at=(datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        )
    )
    mock_lock_factory.return_value = _make_lock_mock()

    db = AsyncMock()
    db.refresh = AsyncMock(side_effect=_make_fake_db_refresh())
    redis = AsyncMock()
    request = _make_request(check_in=check_in, check_out=check_out)

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.price_breakdown is not None
    assert result.price_breakdown.nights == 3
    assert result.price_breakdown.base_price == 750000.0
    assert result.price_breakdown.vat == pytest.approx(142500.0)
    assert result.total_price == pytest.approx(892500.0)
    assert result.currency == "COP"
