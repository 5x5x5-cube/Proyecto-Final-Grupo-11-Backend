"""Tests for the inventory_service SQS consumer (HU4.3)."""

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sqs_consumer import SQSConsumer

ROOM_ID = uuid.uuid4()
BOOKING_ID = uuid.uuid4()


def _make_event(
    *,
    event_type: str = "booking.cancelled",
    entity_type: str = "booking",
    room_id: str | None = str(ROOM_ID),
    check_in: str | None = "2026-05-10",
    check_out: str | None = "2026-05-13",
    booking_id: str = str(BOOKING_ID),
) -> str:
    """Build the SNS-shaped event payload (JSON-encoded body)."""
    booking_data: dict = {"id": booking_id}
    if room_id is not None:
        booking_data["room_id"] = room_id
    if check_in is not None:
        booking_data["check_in"] = check_in
    if check_out is not None:
        booking_data["check_out"] = check_out

    return json.dumps(
        {
            "event_type": event_type,
            "entity_type": entity_type,
            "data": {"booking": booking_data},
        }
    )


@pytest.fixture
def consumer():
    # boto3 client gets created in __init__; we mock it to avoid hitting AWS.
    with patch("app.services.sqs_consumer.boto3.client") as mock_boto:
        mock_boto.return_value = MagicMock()
        yield SQSConsumer()


class TestProcessMessageDispatch:
    async def test_invalid_json_returns_false(self, consumer):
        assert (await consumer.process_message("not-json")) is False

    async def test_non_booking_entity_is_ignored_but_succeeds(self, consumer):
        body = json.dumps({"event_type": "x", "entity_type": "payment", "data": {}})
        assert (await consumer.process_message(body)) is True

    async def test_unrelated_booking_event_is_ignored_but_succeeds(self, consumer):
        body = _make_event(event_type="booking_created")
        # No DB session should be opened
        with patch("app.services.sqs_consumer.async_session_factory") as factory:
            assert (await consumer.process_message(body)) is True
            factory.assert_not_called()

    async def test_booking_cancelled_dispatches_to_handler(self, consumer):
        body = _make_event(event_type="booking.cancelled")
        with patch.object(
            consumer, "_handle_booking_cancelled", new=AsyncMock(return_value=True)
        ) as handler:
            assert (await consumer.process_message(body)) is True
            handler.assert_awaited_once()


class TestHandleBookingCancelled:
    """Validate the actual release-dates side-effect."""

    async def test_releases_dates_for_valid_event(self, consumer):
        # Mock the async session context manager
        session_mock = AsyncMock()
        session_cm = AsyncMock()
        session_cm.__aenter__.return_value = session_mock
        session_cm.__aexit__.return_value = None

        with patch(
            "app.services.sqs_consumer.async_session_factory",
            return_value=session_cm,
        ), patch("app.services.sqs_consumer.release_dates", new=AsyncMock()) as release_mock:
            ok = await consumer._handle_booking_cancelled(
                {
                    "id": str(BOOKING_ID),
                    "room_id": str(ROOM_ID),
                    "check_in": "2026-05-10",
                    "check_out": "2026-05-13",
                }
            )
            assert ok is True
            release_mock.assert_awaited_once()
            args = release_mock.call_args.args
            # release_dates(db, room_id, check_in, check_out)
            assert args[1] == ROOM_ID
            assert args[2] == date(2026, 5, 10)
            assert args[3] == date(2026, 5, 13)
            session_mock.commit.assert_awaited_once()

    async def test_missing_room_id_returns_false(self, consumer):
        with patch("app.services.sqs_consumer.async_session_factory") as factory:
            ok = await consumer._handle_booking_cancelled(
                {
                    "id": str(BOOKING_ID),
                    "check_in": "2026-05-10",
                    "check_out": "2026-05-13",
                }
            )
            assert ok is False
            factory.assert_not_called()

    async def test_missing_dates_returns_false(self, consumer):
        ok = await consumer._handle_booking_cancelled(
            {"id": str(BOOKING_ID), "room_id": str(ROOM_ID)}
        )
        assert ok is False

    async def test_invalid_uuid_returns_false(self, consumer):
        ok = await consumer._handle_booking_cancelled(
            {
                "id": str(BOOKING_ID),
                "room_id": "not-a-uuid",
                "check_in": "2026-05-10",
                "check_out": "2026-05-13",
            }
        )
        assert ok is False

    async def test_invalid_date_returns_false(self, consumer):
        ok = await consumer._handle_booking_cancelled(
            {
                "id": str(BOOKING_ID),
                "room_id": str(ROOM_ID),
                "check_in": "not-a-date",
                "check_out": "2026-05-13",
            }
        )
        assert ok is False

    async def test_db_failure_rolls_back_and_returns_false(self, consumer):
        session_mock = AsyncMock()
        session_cm = AsyncMock()
        session_cm.__aenter__.return_value = session_mock
        session_cm.__aexit__.return_value = None

        with patch(
            "app.services.sqs_consumer.async_session_factory",
            return_value=session_cm,
        ), patch(
            "app.services.sqs_consumer.release_dates",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            ok = await consumer._handle_booking_cancelled(
                {
                    "id": str(BOOKING_ID),
                    "room_id": str(ROOM_ID),
                    "check_in": "2026-05-10",
                    "check_out": "2026-05-13",
                }
            )
            assert ok is False
            session_mock.rollback.assert_awaited_once()
            session_mock.commit.assert_not_awaited()
