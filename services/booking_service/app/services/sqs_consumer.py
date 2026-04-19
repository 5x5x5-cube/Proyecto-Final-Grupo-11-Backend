import json
import logging
import uuid

import boto3
import httpx
from botocore.exceptions import ClientError
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session_factory
from app.models import Booking
from app.schemas import CreateBookingRequest
from app.services.booking_service import create_booking

logger = logging.getLogger(__name__)
settings = get_settings()


class SQSConsumer:
    def __init__(self):
        client_kwargs = {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url
        self.client = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.sqs_queue_url

    async def process_message(self, message_body: str) -> bool:
        try:
            event = json.loads(message_body)
            event_type = event.get("event_type")

            if event_type != "payment_confirmed":
                print(f"Ignoring event type: {event_type}")
                return True

            data = event.get("data", {})
            payment = data.get("payment", {})
            user_id_str = payment.get("userId")
            booking_data = payment.get("bookingData", {})
            payment_id_str = payment.get("paymentId")

            if not user_id_str or not booking_data:
                logger.warning("Missing userId or bookingData in payment_confirmed event")
                return False

            hold_id = booking_data.get("holdId")

            # Idempotency: check if a booking with the same hold_id already exists
            async with async_session_factory() as session:
                if hold_id:
                    result = await session.execute(
                        select(Booking).where(Booking.hold_id == uuid.UUID(hold_id))
                    )
                    existing = result.scalar_one_or_none()
                    if existing:
                        logger.info("Booking already exists for holdId=%s, skipping", hold_id)
                        return True

                request = CreateBookingRequest(
                    roomId=booking_data.get("roomId"),
                    hotelId=booking_data.get("hotelId"),
                    holdId=hold_id,
                    paymentId=payment_id_str,
                    checkIn=booking_data.get("checkIn"),
                    checkOut=booking_data.get("checkOut"),
                    guests=booking_data.get("guests"),
                    basePrice=booking_data.get("basePrice"),
                    taxAmount=booking_data.get("taxAmount"),
                    serviceFee=booking_data.get("serviceFee", "0"),
                    totalPrice=booking_data.get("totalPrice"),
                )

                await create_booking(
                    db=session,
                    user_id=uuid.UUID(user_id_str),
                    request=request,
                )
                logger.info("Booking created for userId=%s, holdId=%s", user_id_str, hold_id)

            # Post-payment: confirm hold in inventory (best-effort)
            if hold_id:
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.put(
                            f"{settings.inventory_service_url}/holds/{hold_id}/confirm"
                        )
                        resp.raise_for_status()
                        logger.info("Hold %s confirmed in inventory", hold_id)
                except Exception as e:
                    logger.warning("Failed to confirm hold %s: %s", hold_id, e)

            # Post-payment: mark cart as completed (best-effort)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.patch(
                        f"{settings.cart_service_url}/api/v1/cart/complete",
                        headers={"X-User-Id": user_id_str},
                    )
                    resp.raise_for_status()
                    logger.info("Cart completed for userId=%s", user_id_str)
            except Exception as e:
                logger.warning("Failed to complete cart for userId=%s: %s", user_id_str, e)

            return True

        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")
            return False
        except Exception as e:
            print(f"Error processing message: {e}")
            return False

    def poll_messages(self):
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=settings.sqs_max_messages,
                WaitTimeSeconds=settings.sqs_poll_interval,
                VisibilityTimeout=settings.sqs_visibility_timeout,
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            if not messages:
                return 0, []

            return len(messages), messages

        except ClientError as e:
            print(f"Error polling SQS: {e}")
            return 0, []
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 0, []

    def delete_message(self, receipt_handle: str):
        self.client.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt_handle)


consumer = SQSConsumer()
