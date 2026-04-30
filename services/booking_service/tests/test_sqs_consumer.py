import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_payment_confirmed_event(
    user_id=None,
    payment_id=None,
    hold_id=None,
):
    return json.dumps(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "payment_confirmed",
            "entity_type": "payment",
            "timestamp": "2026-04-30T12:00:00",
            "data": {
                "payment": {
                    "paymentId": str(payment_id or uuid.uuid4()),
                    "userId": str(user_id or uuid.uuid4()),
                    "amount": 476000.0,
                    "currency": "COP",
                    "transactionId": "TXN-123",
                    "bookingData": {
                        "roomId": str(uuid.uuid4()),
                        "hotelId": str(uuid.uuid4()),
                        "holdId": str(hold_id or uuid.uuid4()),
                        "checkIn": "2026-06-01",
                        "checkOut": "2026-06-05",
                        "guests": 2,
                        "basePrice": "400000",
                        "taxAmount": "76000",
                        "serviceFee": "0",
                        "totalPrice": "476000",
                    },
                }
            },
            "metadata": {
                "retry_count": 0,
                "correlation_id": str(uuid.uuid4()),
                "source_service": "payment-service",
            },
        }
    )


@pytest.fixture
def consumer():
    with patch("app.services.sqs_consumer.boto3"):
        from app.services.sqs_consumer import SQSConsumer

        return SQSConsumer()


class TestBookingCreatedEventPublishing:
    async def test_publishes_lean_booking_created_event(self, consumer):
        """After creating a booking, publishes a lean event with only IDs."""
        payment_id = uuid.uuid4()
        event = _make_payment_confirmed_event(payment_id=payment_id)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        mock_booking_response = MagicMock()
        mock_booking_response.id = uuid.uuid4()
        mock_booking_response.code = "BK-TEST1234"

        with (
            patch("app.services.sqs_consumer.async_session_factory") as mock_factory,
            patch(
                "app.services.sqs_consumer.create_booking",
                new_callable=AsyncMock,
                return_value=mock_booking_response,
            ) as mock_create,
            patch("app.services.sqs_consumer.sns_publisher", new_callable=MagicMock) as mock_sns,
            patch("app.services.sqs_consumer.httpx") as mock_httpx,
        ):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_sns.publish_booking_created = AsyncMock(return_value=True)

            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.put = AsyncMock(return_value=mock_resp)
            mock_client.patch = AsyncMock(return_value=mock_resp)
            mock_httpx.AsyncClient.return_value = mock_client

            result = await consumer.process_message(event)

            assert result is True
            mock_create.assert_called_once()
            mock_sns.publish_booking_created.assert_called_once()

            # Verify the event is lean — only IDs
            call_kwargs = mock_sns.publish_booking_created.call_args[1]
            assert call_kwargs["booking_id"] == str(mock_booking_response.id)
            assert call_kwargs["user_id"] is not None
            assert call_kwargs["payment_id"] == str(payment_id)
            # Should NOT have enriched data keys
            assert "hotel_name" not in call_kwargs
            assert "booking_code" not in call_kwargs

    async def test_skips_non_payment_confirmed(self, consumer):
        event = json.dumps({"event_type": "some_other_event", "entity_type": "payment", "data": {}})
        result = await consumer.process_message(event)
        assert result is True
