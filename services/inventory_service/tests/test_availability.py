import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import RoomNotFoundError
from app.services.availability_service import _date_range, get_room


def test_date_range_single_night():
    check_in = date(2026, 4, 1)
    check_out = date(2026, 4, 2)
    dates = _date_range(check_in, check_out)
    assert dates == [date(2026, 4, 1)]


def test_date_range_multiple_nights():
    check_in = date(2026, 4, 1)
    check_out = date(2026, 4, 4)
    dates = _date_range(check_in, check_out)
    assert len(dates) == 3
    assert dates[0] == date(2026, 4, 1)
    assert dates[-1] == date(2026, 4, 3)


def test_date_range_same_day():
    d = date(2026, 4, 1)
    dates = _date_range(d, d)
    assert dates == []


async def test_get_room_not_found():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock

    with pytest.raises(RoomNotFoundError):
        await get_room(db, uuid.uuid4())


async def test_get_room_found(sample_room):
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_room
    db.execute.return_value = result_mock

    room = await get_room(db, sample_room.id)
    assert room.id == sample_room.id
    assert room.room_type == "Standard"
