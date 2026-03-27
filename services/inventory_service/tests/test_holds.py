import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import HoldNotFoundError
from app.services.hold_service import check_hold, release_hold


async def test_check_hold_no_holds():
    redis = AsyncMock()
    redis.get.return_value = None

    result = await check_hold(
        redis=redis,
        room_id=uuid.uuid4(),
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        user_id=uuid.uuid4(),
    )
    assert result["held"] is False
    assert result["holder_id"] is None


async def test_check_hold_held_by_other_user():
    other_user = uuid.uuid4()
    hold_id = uuid.uuid4()
    room_id = uuid.uuid4()

    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "holdId": str(hold_id),
            "roomId": str(room_id),
            "userId": str(other_user),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
            "createdAt": "2026-03-25T20:00:00+00:00",
        }
    )

    result = await check_hold(
        redis=redis,
        room_id=room_id,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        user_id=uuid.uuid4(),
    )
    assert result["held"] is True
    assert result["holder_id"] == other_user
    assert "same_user" not in result


async def test_check_hold_held_by_same_user():
    user_id = uuid.uuid4()
    hold_id = uuid.uuid4()
    room_id = uuid.uuid4()

    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "holdId": str(hold_id),
            "roomId": str(room_id),
            "userId": str(user_id),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
            "createdAt": "2026-03-25T20:00:00+00:00",
        }
    )

    result = await check_hold(
        redis=redis,
        room_id=room_id,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        user_id=user_id,
    )
    assert result["held"] is True
    assert result["same_user"] is True


async def test_release_hold_not_found():
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute.return_value = result_mock
    redis = AsyncMock()

    with pytest.raises(HoldNotFoundError):
        await release_hold(db=db, redis=redis, hold_id=uuid.uuid4())


async def test_release_hold_already_expired(sample_hold):
    sample_hold.status = "expired"
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = sample_hold
    db.execute.return_value = result_mock
    redis = AsyncMock()

    # Should not raise, just log warning and return
    await release_hold(db=db, redis=redis, hold_id=sample_hold.id)
    # Verify it did NOT call release_dates (no flush/commit)
    db.flush.assert_not_called()
