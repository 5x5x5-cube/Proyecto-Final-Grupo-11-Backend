import json
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.exceptions import HoldNotFoundError, RoomHeldError
from app.models import Hold, Room
from app.services.hold_service import check_hold, create_hold, release_hold


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


async def test_create_hold_releases_existing_hold_on_different_room():
    """
    Hold-per-user upsert: creating a hold for room B when user already has an
    active hold on room A should automatically release the room A hold.
    """
    user_id = uuid.uuid4()
    room_a_id = uuid.uuid4()
    room_b_id = uuid.uuid4()
    hotel_id = uuid.uuid4()

    now = datetime.now(timezone.utc)

    # Existing hold on room A
    old_hold = Hold(
        id=uuid.uuid4(),
        room_id=room_a_id,
        user_id=user_id,
        check_in=date(2026, 5, 1),
        check_out=date(2026, 5, 3),
        status="active",
        expires_at=now + timedelta(minutes=10),
    )

    # Room B that we're creating a new hold for
    room_b = Room(
        id=room_b_id,
        hotel_id=hotel_id,
        room_type="Deluxe",
        room_number="202",
        capacity=2,
        price_per_night=300000,
        tax_rate=0.19,
        total_quantity=1,
    )

    db = AsyncMock()
    redis = AsyncMock()
    redis.get.return_value = None  # No existing Redis hold on room B dates

    # db.execute call sequence:
    # 1. select(Room) — returns room_b
    # 2. check_hold redis calls — handled by redis mock
    # 3. select(Hold) for upsert check — returns old_hold
    # 4. select(Hold) inside release_hold — returns old_hold
    # 5. reserve_dates calls (handled by patch)
    room_result = MagicMock()
    room_result.scalar_one_or_none.return_value = room_b

    old_hold_result = MagicMock()
    old_hold_result.scalar_one_or_none.return_value = old_hold

    released_hold_result = MagicMock()
    released_hold_result.scalar_one_or_none.return_value = old_hold

    # execute call sequence: room lookup, upsert query, release_hold lookup
    db.execute.side_effect = [room_result, old_hold_result, released_hold_result]

    with (
        patch("app.services.hold_service.reserve_dates", new_callable=AsyncMock) as mock_reserve,
        patch("app.services.hold_service.release_dates", new_callable=AsyncMock) as mock_release,
    ):
        await create_hold(
            db=db,
            redis=redis,
            room_id=room_b_id,
            user_id=user_id,
            check_in=date(2026, 6, 1),
            check_out=date(2026, 6, 3),
        )

    # release_dates was called once (for old hold on room A)
    mock_release.assert_called_once()
    # reserve_dates was called once (for new hold on room B)
    mock_reserve.assert_called_once()
    # The old hold was marked expired
    assert old_hold.status == "expired"
