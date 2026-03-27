"""
Edge-case tests for availability and hold services.

All DB and Redis interactions are mocked — no real connections are made.
"""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import RoomUnavailableError
from app.models import Availability, Room
from app.services.availability_service import _date_range, check_availability, reserve_dates
from app.services.hold_service import check_hold

# ---------------------------------------------------------------------------
# Fixed UUIDs
# ---------------------------------------------------------------------------
ROOM_ID = uuid.UUID("b1000000-0000-0000-0000-000000000001")
HOTEL_ID = uuid.UUID("a1000000-0000-0000-0000-000000000001")
USER_A_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
USER_B_ID = uuid.UUID("c2000000-0000-0000-0000-000000000002")
HOLD_A_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_room(total_quantity=1):
    return Room(
        id=ROOM_ID,
        hotel_id=HOTEL_ID,
        room_type="Standard",
        room_number="101",
        capacity=2,
        price_per_night=250000,
        tax_rate=0.19,
        total_quantity=total_quantity,
    )


def make_availability(d: date, available_quantity: int, total_quantity: int = 1):
    return Availability(
        id=uuid.uuid4(),
        room_id=ROOM_ID,
        date=d,
        total_quantity=total_quantity,
        available_quantity=available_quantity,
    )


def make_db_with_scalar(value):
    """Return a mock AsyncSession whose .execute() returns a scalar result."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = value
    db.execute.return_value = result_mock
    return db


# ---------------------------------------------------------------------------
# Edge case 1: same-day checkout → _date_range is empty → reserve_dates is a no-op
# ---------------------------------------------------------------------------


def test_date_range_same_day_is_empty():
    """_date_range(d, d) must return an empty list (0 nights stay)."""
    d = date(2026, 4, 1)
    assert _date_range(d, d) == []


async def test_reserve_dates_same_day_is_noop():
    """reserve_dates with check_in == check_out should do nothing to the DB."""
    room = make_room()
    db = AsyncMock()

    # get_room is called internally; provide a valid room so it doesn't raise
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = room
    db.execute.return_value = result_mock

    same_day = date(2026, 4, 1)
    await reserve_dates(db, ROOM_ID, same_day, same_day)

    # flush should still be called once (end-of-function), but execute should only
    # be called for the get_room SELECT — no per-date availability rows.
    db.execute.assert_called_once()  # only the get_room query
    db.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Edge case 2: overlapping partial dates — User A holds Apr 1–3, User B checks Apr 2–4
# ---------------------------------------------------------------------------


async def test_check_hold_partial_overlap_detects_conflict():
    """
    User A holds 2026-04-01 and 2026-04-02.
    User B requests 2026-04-02 to 2026-04-04.
    The first date in B's range (Apr 2) is free in Redis (key not set),
    but the second date (Apr 3 in a longer range) is not the conflict here —
    instead Apr 2 key IS set by user A.  check_hold should return held=True.
    """
    hold_data = json.dumps(
        {
            "holdId": str(HOLD_A_ID),
            "roomId": str(ROOM_ID),
            "userId": str(USER_A_ID),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
            "createdAt": "2026-03-25T12:00:00+00:00",
        }
    )

    # Apr 2 is held by user A; Apr 3 would not need to be checked
    async def redis_get_side_effect(key):
        # room_hold:<room>:2026-04-02 → user A's hold
        if "2026-04-02" in key:
            return hold_data
        return None

    redis = AsyncMock()
    redis.get.side_effect = redis_get_side_effect

    result = await check_hold(
        redis=redis,
        room_id=ROOM_ID,
        check_in=date(2026, 4, 2),
        check_out=date(2026, 4, 4),
        user_id=USER_B_ID,
    )

    assert result["held"] is True
    assert result["holder_id"] == USER_A_ID
    assert result["hold_id"] == HOLD_A_ID
    assert "same_user" not in result


# ---------------------------------------------------------------------------
# Edge case 3: check_availability raises RoomUnavailableError when all
#              dates have available_quantity == 0
# ---------------------------------------------------------------------------


async def test_check_availability_all_dates_zero_quantity_raises():
    """check_availability raises RoomUnavailableError when every requested date has qty=0."""
    rows = [
        make_availability(date(2026, 4, 1), available_quantity=0),
        make_availability(date(2026, 4, 2), available_quantity=0),
    ]

    db = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    db.execute.return_value = result_mock

    with pytest.raises(RoomUnavailableError) as exc_info:
        await check_availability(db, ROOM_ID, date(2026, 4, 1), date(2026, 4, 3))

    error = exc_info.value
    assert error.room_id == str(ROOM_ID)
    assert "2026-04-01" in error.dates
    assert "2026-04-02" in error.dates


async def test_check_availability_mixed_zero_and_available_raises():
    """check_availability raises when at least one date has qty=0 and no dates are missing."""
    rows = [
        make_availability(date(2026, 4, 1), available_quantity=1),
        make_availability(date(2026, 4, 2), available_quantity=0),
    ]

    db = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    db.execute.return_value = result_mock

    with pytest.raises(RoomUnavailableError) as exc_info:
        await check_availability(db, ROOM_ID, date(2026, 4, 1), date(2026, 4, 3))

    error = exc_info.value
    assert "2026-04-02" in error.dates
    assert "2026-04-01" not in error.dates


# ---------------------------------------------------------------------------
# Edge case 4: check_hold with multiple dates — conflict only on second date
# ---------------------------------------------------------------------------


async def test_check_hold_conflict_on_second_date_only():
    """
    First date in range has no hold, second date is held by another user.
    check_hold must still detect the conflict on the second date.
    """
    hold_data = json.dumps(
        {
            "holdId": str(HOLD_A_ID),
            "roomId": str(ROOM_ID),
            "userId": str(USER_A_ID),
            "checkIn": "2026-04-02",
            "checkOut": "2026-04-03",
            "createdAt": "2026-03-25T12:00:00+00:00",
        }
    )

    async def redis_get_side_effect(key):
        # Apr 1 is free; Apr 2 is held by user A
        if "2026-04-02" in key:
            return hold_data
        return None

    redis = AsyncMock()
    redis.get.side_effect = redis_get_side_effect

    # User B checks Apr 1 → Apr 3 (covers Apr 1 and Apr 2)
    result = await check_hold(
        redis=redis,
        room_id=ROOM_ID,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        user_id=USER_B_ID,
    )

    assert result["held"] is True
    assert result["holder_id"] == USER_A_ID
    assert result["hold_id"] == HOLD_A_ID


async def test_check_hold_all_dates_free_returns_not_held():
    """When every date in the range is free in Redis, check_hold returns held=False."""
    redis = AsyncMock()
    redis.get.return_value = None  # every key returns None

    result = await check_hold(
        redis=redis,
        room_id=ROOM_ID,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 4),  # 3 nights
        user_id=USER_B_ID,
    )

    assert result["held"] is False
    assert result["holder_id"] is None
    assert result["hold_id"] is None
    # Redis must have been queried once per night (3 calls)
    assert redis.get.call_count == 3


# ---------------------------------------------------------------------------
# Edge case 5: single-night stay — _date_range generates exactly one date
# ---------------------------------------------------------------------------


def test_date_range_one_night():
    """A check-in/check-out spanning exactly one night yields a single date."""
    dates = _date_range(date(2026, 4, 1), date(2026, 4, 2))
    assert dates == [date(2026, 4, 1)]


def test_date_range_excludes_checkout_date():
    """check_out date itself must NOT appear in the generated range (exclusive end)."""
    dates = _date_range(date(2026, 4, 1), date(2026, 4, 4))
    assert date(2026, 4, 4) not in dates
    assert len(dates) == 3
