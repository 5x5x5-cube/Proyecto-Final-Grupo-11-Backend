import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Hold
from app.tasks.cleanup import cleanup_expired_holds


def _make_expired_hold(room_id=None):
    return Hold(
        id=uuid.uuid4(),
        room_id=room_id or uuid.uuid4(),
        user_id=uuid.uuid4(),
        check_in=date.today(),
        check_out=date.today() + timedelta(days=2),
        status="active",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )


@patch("app.tasks.cleanup.get_redis")
@patch("app.tasks.cleanup.async_session_factory")
async def test_cleanup_finds_and_cleans_expired_holds(mock_session_factory, mock_get_redis):
    hold = _make_expired_hold()

    # Mock DB session
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [hold]
    db.execute.return_value = result_mock
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    # Mock Redis
    redis = AsyncMock()
    mock_get_redis.return_value = redis

    # Mock release_dates to avoid DB interaction
    with patch("app.tasks.cleanup.release_dates", new_callable=AsyncMock) as mock_release:
        cleaned = await cleanup_expired_holds()

    assert cleaned == 1
    assert hold.status == "expired"
    mock_release.assert_called_once()
    db.commit.assert_called_once()


@patch("app.tasks.cleanup.get_redis")
@patch("app.tasks.cleanup.async_session_factory")
async def test_cleanup_no_expired_holds(mock_session_factory, mock_get_redis):
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    db.execute.return_value = result_mock
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_get_redis.return_value = AsyncMock()

    cleaned = await cleanup_expired_holds()

    assert cleaned == 0
    db.commit.assert_not_called()


@patch("app.tasks.cleanup.get_redis")
@patch("app.tasks.cleanup.async_session_factory")
async def test_cleanup_handles_individual_hold_error(mock_session_factory, mock_get_redis):
    hold1 = _make_expired_hold()
    hold2 = _make_expired_hold()

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [hold1, hold2]
    db.execute.return_value = result_mock
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    redis = AsyncMock()
    mock_get_redis.return_value = redis

    # First hold fails, second succeeds
    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("DB error on first hold")

    with patch("app.tasks.cleanup.release_dates", new_callable=AsyncMock, side_effect=side_effect):
        cleaned = await cleanup_expired_holds()

    # Only second hold was cleaned
    assert cleaned == 1
    db.commit.assert_called_once()
