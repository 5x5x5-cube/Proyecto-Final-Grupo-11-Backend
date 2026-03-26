import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.exceptions import InventoryServiceError
from app.schemas import CreateBookingRequest
from app.services.booking_service import create_booking


def _make_request():
    return CreateBookingRequest(
        room_id=uuid.UUID("b1000000-0000-0000-0000-000000000001"),
        hotel_id=uuid.UUID("a1000000-0000-0000-0000-000000000001"),
        check_in=date.today() + timedelta(days=1),
        check_out=date.today() + timedelta(days=3),
        guests=2,
        user_id=uuid.UUID("c1000000-0000-0000-0000-000000000001"),
    )


def _make_hold_response(hold_id=None):
    hid = hold_id or str(uuid.uuid4())
    return {
        "id": hid,
        "room_id": "b1000000-0000-0000-0000-000000000001",
        "user_id": "c1000000-0000-0000-0000-000000000001",
        "check_in": (date.today() + timedelta(days=1)).isoformat(),
        "check_out": (date.today() + timedelta(days=3)).isoformat(),
        "status": "active",
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        "price_per_night": 250000,
        "tax_rate": 0.19,
        "room_type": "Standard",
    }


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_create_booking_success(mock_lock_factory, mock_inventory):
    # Setup mocks — use AsyncMock for async functions
    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    mock_inventory.create_hold = AsyncMock(return_value=_make_hold_response())

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    mock_lock_factory.return_value = mock_lock

    db = AsyncMock()

    # Mock db.refresh to populate auto-generated fields on the booking
    async def fake_refresh(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.code is None:
            obj.code = "BK-TEST1234"
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if obj.updated_at is None:
            obj.updated_at = datetime.now(timezone.utc)

    db.refresh = AsyncMock(side_effect=fake_refresh)

    redis = AsyncMock()
    request = _make_request()

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.status == "pending"
    assert result.guests == 2
    assert result.total_price > 0
    assert result.price_breakdown is not None
    assert result.price_breakdown.nights == 2
    db.add.assert_called_once()
    db.commit.assert_called_once()


@patch("app.services.booking_service.inventory_client")
async def test_create_booking_room_held_by_other(mock_inventory):
    mock_inventory.check_hold = AsyncMock(
        return_value={
            "held": True,
            "holder_id": str(uuid.uuid4()),
            "hold_id": str(uuid.uuid4()),
        }
    )

    db = AsyncMock()
    redis = AsyncMock()
    request = _make_request()

    with pytest.raises(InventoryServiceError, match="being processed"):
        await create_booking(db=db, redis=redis, request=request)


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_create_booking_inventory_unavailable(mock_lock_factory, mock_inventory):
    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    mock_inventory.create_hold = AsyncMock(
        side_effect=InventoryServiceError("Room unavailable", status_code=409)
    )

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    mock_lock_factory.return_value = mock_lock

    db = AsyncMock()
    redis = AsyncMock()
    request = _make_request()

    with pytest.raises(InventoryServiceError):
        await create_booking(db=db, redis=redis, request=request)


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_create_booking_db_failure_compensates(mock_lock_factory, mock_inventory):
    hold_id = str(uuid.uuid4())
    mock_inventory.check_hold = AsyncMock(return_value={"held": False})
    mock_inventory.create_hold = AsyncMock(return_value=_make_hold_response(hold_id))
    mock_inventory.release_hold = AsyncMock()

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    mock_lock_factory.return_value = mock_lock

    db = AsyncMock()
    db.commit.side_effect = Exception("DB connection lost")
    redis = AsyncMock()
    request = _make_request()

    with pytest.raises(Exception, match="DB connection lost"):
        await create_booking(db=db, redis=redis, request=request)

    # Verify compensation was called
    mock_inventory.release_hold.assert_called_once_with(uuid.UUID(hold_id))


@patch("app.services.booking_service.inventory_client")
async def test_same_user_re_reserve_returns_existing_booking(mock_inventory):
    """When same user already holds the room, return the existing pending booking."""
    hold_id = uuid.uuid4()
    mock_inventory.check_hold = AsyncMock(
        return_value={
            "held": True,
            "same_user": True,
            "holder_id": str(uuid.UUID("c1000000-0000-0000-0000-000000000001")),
            "hold_id": str(hold_id),
        }
    )

    # Mock DB to return an existing booking
    from unittest.mock import MagicMock

    from app.models import Booking

    existing_booking = Booking(
        id=uuid.uuid4(),
        code="BK-EXISTING",
        user_id=uuid.UUID("c1000000-0000-0000-0000-000000000001"),
        hotel_id=uuid.UUID("a1000000-0000-0000-0000-000000000001"),
        room_id=uuid.UUID("b1000000-0000-0000-0000-000000000001"),
        hold_id=hold_id,
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

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing_booking
    db.execute.return_value = result_mock

    redis = AsyncMock()
    request = _make_request()

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.code == "BK-EXISTING"
    assert result.status == "pending"
    # Should NOT have called create_hold (no new hold needed)
    mock_inventory.create_hold.assert_not_called()


@patch("app.services.booking_service.inventory_client")
@patch("app.services.booking_service.create_booking_lock")
async def test_same_user_hold_but_no_booking_creates_new(mock_lock_factory, mock_inventory):
    """Edge case: same user has hold but booking record is missing — create new."""
    hold_id = uuid.uuid4()
    mock_inventory.check_hold = AsyncMock(
        return_value={
            "held": True,
            "same_user": True,
            "holder_id": str(uuid.UUID("c1000000-0000-0000-0000-000000000001")),
            "hold_id": str(hold_id),
        }
    )
    mock_inventory.create_hold = AsyncMock(return_value=_make_hold_response())

    # DB returns no existing booking for this hold
    from unittest.mock import MagicMock

    db = AsyncMock()
    # First call: idempotency check returns None
    idempotency_result = MagicMock()
    idempotency_result.scalar_one_or_none.return_value = None
    db.execute.return_value = idempotency_result

    # Mock db.refresh to populate auto-generated fields
    async def fake_refresh(obj):
        if obj.id is None:
            obj.id = uuid.uuid4()
        if obj.code is None:
            obj.code = "BK-NEW12345"
        if obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        if obj.updated_at is None:
            obj.updated_at = datetime.now(timezone.utc)

    db.refresh = AsyncMock(side_effect=fake_refresh)

    mock_lock = AsyncMock()
    mock_lock.__aenter__ = AsyncMock(return_value=mock_lock)
    mock_lock.__aexit__ = AsyncMock(return_value=False)
    mock_lock_factory.return_value = mock_lock

    redis = AsyncMock()
    request = _make_request()

    result = await create_booking(db=db, redis=redis, request=request)

    assert result.status == "pending"
    # Should have proceeded to create a new hold + booking
    mock_inventory.create_hold.assert_called_once()
