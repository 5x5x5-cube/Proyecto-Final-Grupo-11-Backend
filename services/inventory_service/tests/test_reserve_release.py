import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import RoomNotFoundError, RoomUnavailableError
from app.models import Availability, Room
from app.services.availability_service import release_dates, reserve_dates


def _make_room(room_id, total_quantity=1):
    return Room(
        id=room_id,
        hotel_id=uuid.uuid4(),
        room_type="Standard",
        room_number="101",
        capacity=2,
        price_per_night=250000,
        tax_rate=0.19,
        total_quantity=total_quantity,
    )


def _make_availability(room_id, d, available=1, total=1):
    return Availability(
        id=uuid.uuid4(),
        room_id=room_id,
        date=d,
        available_quantity=available,
        total_quantity=total,
    )


async def test_reserve_dates_decrements_availability():
    room_id = uuid.uuid4()
    check_in = date(2026, 4, 1)
    check_out = date(2026, 4, 3)
    room = _make_room(room_id, total_quantity=5)
    avail1 = _make_availability(room_id, date(2026, 4, 1), available=5, total=5)
    avail2 = _make_availability(room_id, date(2026, 4, 2), available=5, total=5)

    db = AsyncMock()
    call_index = 0

    def execute_side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        result = MagicMock()
        # First call: get_room (SELECT Room)
        if call_index == 1:
            result.scalar_one_or_none.return_value = room
        # Second call: SELECT FOR UPDATE avail1
        elif call_index == 2:
            result.scalar_one_or_none.return_value = avail1
        # Third call: SELECT FOR UPDATE avail2
        elif call_index == 3:
            result.scalar_one_or_none.return_value = avail2
        return result

    db.execute = AsyncMock(side_effect=execute_side_effect)

    await reserve_dates(db, room_id, check_in, check_out)

    assert avail1.available_quantity == 4
    assert avail2.available_quantity == 4
    db.flush.assert_called()


async def test_reserve_dates_raises_when_unavailable():
    room_id = uuid.uuid4()
    room = _make_room(room_id)
    avail = _make_availability(room_id, date(2026, 4, 1), available=0)

    db = AsyncMock()
    call_index = 0

    def execute_side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        result = MagicMock()
        if call_index == 1:
            result.scalar_one_or_none.return_value = room
        elif call_index == 2:
            result.scalar_one_or_none.return_value = avail
        return result

    db.execute = AsyncMock(side_effect=execute_side_effect)

    with pytest.raises(RoomUnavailableError):
        await reserve_dates(db, room_id, date(2026, 4, 1), date(2026, 4, 2))


async def test_reserve_dates_room_not_found():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result

    with pytest.raises(RoomNotFoundError):
        await reserve_dates(db, uuid.uuid4(), date(2026, 4, 1), date(2026, 4, 2))


async def test_release_dates_increments_availability():
    room_id = uuid.uuid4()
    room = _make_room(room_id, total_quantity=5)
    avail1 = _make_availability(room_id, date(2026, 4, 1), available=3, total=5)
    avail2 = _make_availability(room_id, date(2026, 4, 2), available=3, total=5)

    db = AsyncMock()
    call_index = 0

    def execute_side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        result = MagicMock()
        if call_index == 1:
            result.scalar_one_or_none.return_value = avail1
        elif call_index == 2:
            result.scalar_one_or_none.return_value = room
        elif call_index == 3:
            result.scalar_one_or_none.return_value = avail2
        elif call_index == 4:
            result.scalar_one_or_none.return_value = room
        return result

    db.execute = AsyncMock(side_effect=execute_side_effect)

    await release_dates(db, room_id, date(2026, 4, 1), date(2026, 4, 3))

    assert avail1.available_quantity == 4
    assert avail2.available_quantity == 4


async def test_release_dates_at_max_capacity_is_noop():
    room_id = uuid.uuid4()
    room = _make_room(room_id, total_quantity=5)
    avail = _make_availability(room_id, date(2026, 4, 1), available=5, total=5)

    db = AsyncMock()
    call_index = 0

    def execute_side_effect(*args, **kwargs):
        nonlocal call_index
        call_index += 1
        result = MagicMock()
        if call_index == 1:
            result.scalar_one_or_none.return_value = avail
        elif call_index == 2:
            result.scalar_one_or_none.return_value = room
        return result

    db.execute = AsyncMock(side_effect=execute_side_effect)

    await release_dates(db, room_id, date(2026, 4, 1), date(2026, 4, 2))

    # Should NOT increment past total_quantity
    assert avail.available_quantity == 5
