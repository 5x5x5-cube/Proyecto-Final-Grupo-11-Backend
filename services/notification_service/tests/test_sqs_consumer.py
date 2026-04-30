import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sqs_consumer import SQSConsumer


def _make_booking_created_event(
    booking_id=None,
    user_id=None,
    payment_id=None,
):
    """Lean event — only IDs, no enriched data."""
    return json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "booking_created",
            "entity_type": "booking",
            "timestamp": "2026-04-30T12:00:00",
            "data": {
                "booking": {
                    "id": str(booking_id or uuid.uuid4()),
                    "user_id": str(user_id or uuid.uuid4()),
                    "payment_id": str(payment_id or uuid.uuid4()),
                }
            },
            "metadata": {
                "retry_count": 0,
                "correlation_id": str(uuid.uuid4()),
                "source_service": "booking-service",
            },
        }
    )


def _make_booking_status_updated_event(status="confirmed"):
    return json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "booking_status_updated",
            "entity_type": "booking",
            "timestamp": "2026-04-30T12:00:00",
            "data": {
                "booking": {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "hotel_id": str(uuid.uuid4()),
                    "status": status,
                    "hotel_name": "Hotel Test",
                    "check_in": "2026-06-01",
                    "check_out": "2026-06-05",
                }
            },
            "metadata": {
                "retry_count": 0,
                "correlation_id": str(uuid.uuid4()),
                "source_service": "booking-service",
            },
        }
    )


MOCK_BOOKING_RESPONSE = {
    "id": str(uuid.uuid4()),
    "code": "BK-TEST1234",
    "userId": str(uuid.uuid4()),
    "hotelId": str(uuid.uuid4()),
    "roomId": str(uuid.uuid4()),
    "hotelName": "Hotel Paradise",
    "roomName": "Suite Premium",
    "checkIn": "2026-06-01",
    "checkOut": "2026-06-05",
    "guests": 2,
    "totalPrice": 476000.0,
    "currency": "COP",
    "priceBreakdown": {
        "basePrice": 400000.0,
        "vat": 76000.0,
        "serviceFee": 0,
        "totalPrice": 476000.0,
    },
}

MOCK_PAYMENT_RESPONSE = {
    "paymentId": str(uuid.uuid4()),
    "status": "approved",
    "amount": 476000.0,
    "currency": "COP",
    "transactionId": "TXN-ABC123",
    "paymentMethod": {
        "id": str(uuid.uuid4()),
        "methodType": "credit_card",
        "displayLabel": "Visa \u2022\u2022\u2022\u2022 4242",
        "cardLast4": "4242",
        "cardBrand": "visa",
    },
}


def _mock_session(db_mock):
    @asynccontextmanager
    async def _get_session():
        yield db_mock

    return _get_session


@pytest.fixture
def consumer():
    with patch("app.services.sqs_consumer.boto3"):
        return SQSConsumer()


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result
    return session


class TestBookingCreatedHandler:
    async def test_sends_email_on_booking_created(self, consumer, mock_db_session):
        event = _make_booking_created_event()
        consumer._get_session = _mock_session(mock_db_session)

        with (
            patch(
                "app.services.sqs_consumer.get_user_info",
                new_callable=AsyncMock,
                return_value={"email": "user@test.com", "name": "Test User"},
            ) as mock_user,
            patch(
                "app.services.sqs_consumer.get_booking_info",
                new_callable=AsyncMock,
                return_value=MOCK_BOOKING_RESPONSE,
            ) as mock_booking,
            patch(
                "app.services.sqs_consumer.get_payment_info",
                new_callable=AsyncMock,
                return_value=MOCK_PAYMENT_RESPONSE,
            ) as mock_payment,
            patch("app.services.sqs_consumer.email_service", new_callable=MagicMock) as mock_email,
            patch("app.services.sqs_consumer.build_payment_confirmation_email") as mock_builder,
        ):
            mock_email.send_email = AsyncMock(return_value=True)
            mock_builder.return_value = {
                "subject": "Confirmacion de reserva BK-TEST1234 - TravelHub",
                "html": "<h1>Test</h1>",
            }

            result = await consumer.process_message(event)

            assert result is True
            mock_user.assert_called_once()
            mock_booking.assert_called_once()
            mock_payment.assert_called_once()
            mock_email.send_email.assert_called_once_with(
                to="user@test.com",
                subject="Confirmacion de reserva BK-TEST1234 - TravelHub",
                html_body="<h1>Test</h1>",
            )
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    async def test_idempotency_skips_duplicate(self, consumer):
        event = _make_booking_created_event()

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # existing record
        mock_db.execute.return_value = mock_result
        consumer._get_session = _mock_session(mock_db)

        with (
            patch("app.services.sqs_consumer.get_user_info", new_callable=AsyncMock) as mock_user,
            patch("app.services.sqs_consumer.email_service", new_callable=MagicMock) as mock_email,
        ):
            mock_email.send_email = AsyncMock()

            result = await consumer.process_message(event)

            assert result is True
            mock_user.assert_not_called()
            mock_email.send_email.assert_not_called()

    async def test_skips_email_when_no_user_email(self, consumer, mock_db_session):
        event = _make_booking_created_event()
        consumer._get_session = _mock_session(mock_db_session)

        with (
            patch(
                "app.services.sqs_consumer.get_user_info",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.sqs_consumer.email_service", new_callable=MagicMock) as mock_email,
        ):
            mock_email.send_email = AsyncMock()

            result = await consumer.process_message(event)

            assert result is True
            mock_email.send_email.assert_not_called()

    async def test_retries_when_booking_not_found(self, consumer, mock_db_session):
        event = _make_booking_created_event()
        consumer._get_session = _mock_session(mock_db_session)

        with (
            patch(
                "app.services.sqs_consumer.get_user_info",
                new_callable=AsyncMock,
                return_value={"email": "user@test.com", "name": "User"},
            ),
            patch(
                "app.services.sqs_consumer.get_booking_info",
                new_callable=AsyncMock,
                return_value=None,  # Booking not found yet
            ),
            patch("app.services.sqs_consumer.email_service", new_callable=MagicMock) as mock_email,
        ):
            mock_email.send_email = AsyncMock()

            result = await consumer.process_message(event)

            assert result is False  # Will trigger SQS retry
            mock_email.send_email.assert_not_called()

    async def test_saves_failed_delivery(self, consumer, mock_db_session):
        event = _make_booking_created_event()
        consumer._get_session = _mock_session(mock_db_session)

        with (
            patch(
                "app.services.sqs_consumer.get_user_info",
                new_callable=AsyncMock,
                return_value={"email": "user@test.com", "name": "User"},
            ),
            patch(
                "app.services.sqs_consumer.get_booking_info",
                new_callable=AsyncMock,
                return_value=MOCK_BOOKING_RESPONSE,
            ),
            patch(
                "app.services.sqs_consumer.get_payment_info",
                new_callable=AsyncMock,
                return_value=MOCK_PAYMENT_RESPONSE,
            ),
            patch("app.services.sqs_consumer.email_service", new_callable=MagicMock) as mock_email,
            patch("app.services.sqs_consumer.build_payment_confirmation_email") as mock_builder,
        ):
            mock_email.send_email = AsyncMock(return_value=False)
            mock_builder.return_value = {"subject": "Test", "html": "<p>Test</p>"}

            result = await consumer.process_message(event)

            assert result is True
            saved_notification = mock_db_session.add.call_args[0][0]
            assert saved_notification.delivered is False
            assert saved_notification.error_message == "Failed to send email"


class TestBookingStatusUpdatedHandler:
    async def test_still_sends_push_notification(self, consumer):
        event = _make_booking_status_updated_event(status="confirmed")

        mock_db = AsyncMock()
        mock_tokens_result = MagicMock()
        mock_tokens_result.scalars.return_value.all.return_value = [
            MagicMock(expo_push_token="ExponentPushToken[xxx]")
        ]
        mock_db.execute.return_value = mock_tokens_result
        consumer._get_session = _mock_session(mock_db)

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock(
                return_value={"success": 1, "failed": 0, "invalid_tokens": []}
            )

            result = await consumer.process_message(event)

            assert result is True
            mock_push.send_push_notification.assert_called_once()


class TestEventDispatch:
    async def test_skips_non_booking_entity(self, consumer):
        event = json.dumps({"event_type": "something", "entity_type": "payment", "data": {}})
        result = await consumer.process_message(event)
        assert result is True

    async def test_skips_unknown_event_type(self, consumer):
        event = json.dumps(
            {"event_type": "unknown_event", "entity_type": "booking", "data": {"booking": {}}}
        )
        result = await consumer.process_message(event)
        assert result is True

    async def test_handles_invalid_json(self, consumer):
        result = await consumer.process_message("not valid json")
        assert result is False
