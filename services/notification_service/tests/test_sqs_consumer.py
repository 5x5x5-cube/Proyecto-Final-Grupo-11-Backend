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


# ---------------------------------------------------------------------------
# HU4.3 — booking.cancelled handler (refund notification)
# ---------------------------------------------------------------------------


def _make_booking_cancelled_event(
    *,
    refund_status: str = "processed",
    refund_amount: str = "62000",
    currency: str = "COP",
    user_id: uuid.UUID | None = None,
    booking_id: uuid.UUID | None = None,
) -> str:
    return json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "booking.cancelled",
            "entity_type": "booking",
            "timestamp": "2026-04-30T12:00:00",
            "data": {
                "booking": {
                    "id": str(booking_id or uuid.uuid4()),
                    "user_id": str(user_id or uuid.uuid4()),
                    "room_id": str(uuid.uuid4()),
                    "hotel_id": str(uuid.uuid4()),
                    "check_in": "2026-06-01",
                    "check_out": "2026-06-05",
                    "currency": currency,
                    "refund_amount": refund_amount,
                    "refund_percentage": 0.5,
                    "refund_status": refund_status,
                }
            },
            "metadata": {
                "retry_count": 0,
                "correlation_id": str(uuid.uuid4()),
                "source_service": "booking-service",
            },
        }
    )


class TestBookingCancelledHandler:
    """booking.cancelled → push notification with the refund outcome (HU4.3 CA5)."""

    async def test_processed_refund_pushes_with_amount_and_eta(self, consumer, mock_db_session):
        event = _make_booking_cancelled_event(refund_status="processed", refund_amount="62000")
        consumer._get_session = _mock_session(mock_db_session)
        consumer.get_user_push_tokens = AsyncMock(return_value=["ExpoPushToken[abc]"])

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock(
                return_value={"success": 1, "failed": 0, "invalid_tokens": []}
            )

            assert (await consumer.process_message(event)) is True
            mock_push.send_push_notification.assert_called_once()
            kwargs = mock_push.send_push_notification.call_args.kwargs
            assert "Reembolso" in kwargs["title"]
            assert "62000" in kwargs["body"]
            assert "5 a 10" in kwargs["body"]
            assert kwargs["data"]["refundStatus"] == "processed"

    async def test_no_refund_uses_policy_message(self, consumer, mock_db_session):
        event = _make_booking_cancelled_event(refund_status="no_refund", refund_amount="0")
        consumer._get_session = _mock_session(mock_db_session)
        consumer.get_user_push_tokens = AsyncMock(return_value=["ExpoPushToken[abc]"])

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock(
                return_value={"success": 1, "failed": 0, "invalid_tokens": []}
            )

            assert (await consumer.process_message(event)) is True
            kwargs = mock_push.send_push_notification.call_args.kwargs
            assert kwargs["title"] == "Reserva cancelada"
            assert "no aplica reembolso" in kwargs["body"]

    async def test_failed_refund_uses_failure_message(self, consumer, mock_db_session):
        event = _make_booking_cancelled_event(refund_status="failed")
        consumer._get_session = _mock_session(mock_db_session)
        consumer.get_user_push_tokens = AsyncMock(return_value=["ExpoPushToken[abc]"])

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock(
                return_value={"success": 1, "failed": 0, "invalid_tokens": []}
            )

            assert (await consumer.process_message(event)) is True
            body = mock_push.send_push_notification.call_args.kwargs["body"]
            assert "inconveniente con el reembolso" in body

    async def test_no_tokens_returns_true_without_pushing(self, consumer, mock_db_session):
        """If the user has no devices we don't fail — just skip silently."""
        event = _make_booking_cancelled_event()
        consumer._get_session = _mock_session(mock_db_session)
        consumer.get_user_push_tokens = AsyncMock(return_value=[])

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock()
            assert (await consumer.process_message(event)) is True
            mock_push.send_push_notification.assert_not_called()

    async def test_missing_required_fields_returns_false(self, consumer, mock_db_session):
        """Without user_id or booking id we can't deliver — flag for retry."""
        event = json.dumps(
            {
                "event_type": "booking.cancelled",
                "entity_type": "booking",
                "data": {"booking": {"refund_status": "processed"}},
            }
        )
        consumer._get_session = _mock_session(mock_db_session)
        result = await consumer.process_message(event)
        assert result is False

    async def test_history_records_refund_metadata(self, consumer, mock_db_session):
        """Notification history must persist refund info under extra_data."""
        event = _make_booking_cancelled_event(refund_status="processed", refund_amount="62000")
        consumer._get_session = _mock_session(mock_db_session)
        consumer.get_user_push_tokens = AsyncMock(return_value=["ExpoPushToken[abc]"])
        consumer.save_notification_history = AsyncMock()

        with patch(
            "app.services.sqs_consumer.expo_push_service", new_callable=MagicMock
        ) as mock_push:
            mock_push.send_push_notification = AsyncMock(
                return_value={"success": 1, "failed": 0, "invalid_tokens": []}
            )

            await consumer.process_message(event)

            consumer.save_notification_history.assert_awaited_once()
            kwargs = consumer.save_notification_history.call_args.kwargs
            assert kwargs["notification_type"] == "booking_cancelled_refund_processed"
            assert kwargs["extra_data"]["refund_status"] == "processed"
            assert kwargs["extra_data"]["refund_amount"] == "62000"
            assert kwargs["extra_data"]["currency"] == "COP"
