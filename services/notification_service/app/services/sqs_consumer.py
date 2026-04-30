import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..config import settings
from ..models import NotificationHistory, PushToken
from .data_enrichment import get_booking_info, get_payment_info, get_user_info
from .email_builder import build_payment_confirmation_email
from .email_service import email_service
from .expo_push import expo_push_service
from .notification_builder import build_booking_notification

logger = logging.getLogger(__name__)


class SQSConsumer:
    def __init__(self):
        client_kwargs = {
            "region_name": settings.aws_region,
        }
        if settings.aws_access_key_id and settings.aws_access_key_id != "test":
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        self.client = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.sqs_queue_url

    @asynccontextmanager
    async def _get_session(self):
        """Create a fresh engine+session per call — safe for background threads."""
        engine = create_async_engine(settings.database_url, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            try:
                yield session
            finally:
                await engine.dispose()

    async def get_user_push_tokens(self, db: AsyncSession, user_id: uuid.UUID) -> list[str]:
        """Get all active push tokens for a user."""
        result = await db.execute(select(PushToken).where(PushToken.user_id == user_id))
        tokens = result.scalars().all()
        return [token.expo_push_token for token in tokens]

    async def save_notification_history(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        booking_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        delivered: bool,
        error_message: str | None = None,
        extra_data: dict | None = None,
    ):
        """Save notification to history."""
        notification = NotificationHistory(
            user_id=user_id,
            booking_id=booking_id,
            notification_type=notification_type,
            title=title,
            body=body,
            delivered=delivered,
            error_message=error_message,
            extra_data=extra_data,
        )
        db.add(notification)
        await db.commit()

    async def remove_invalid_tokens(self, db: AsyncSession, invalid_tokens: list[str]):
        """Remove invalid/unregistered tokens from database."""
        for token in invalid_tokens:
            result = await db.execute(select(PushToken).where(PushToken.expo_push_token == token))
            push_token = result.scalar_one_or_none()
            if push_token:
                await db.delete(push_token)
                logger.info(f"Removed invalid token: {token}")
        await db.commit()

    async def _check_email_already_sent(self, db: AsyncSession, payment_id: str) -> bool:
        """Check if a payment confirmation email was already sent for this payment."""
        result = await db.execute(
            select(NotificationHistory).where(
                NotificationHistory.notification_type == "email_payment_confirmation",
                NotificationHistory.extra_data["payment_id"].astext == payment_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _handle_booking_status_updated(self, booking_data: dict) -> bool:
        """Handle booking_status_updated events — send push notification."""
        user_id_str = booking_data.get("user_id")
        booking_id_str = booking_data.get("id")
        new_status = booking_data.get("status")

        if not user_id_str or not booking_id_str or not new_status:
            logger.error("Missing required fields in booking_status_updated event")
            return False

        user_id = uuid.UUID(user_id_str)
        booking_id = uuid.UUID(booking_id_str)

        async with self._get_session() as db:
            tokens = await self.get_user_push_tokens(db, user_id)

            if not tokens:
                logger.info(f"No push tokens found for user {user_id}")
                return True

            notification = build_booking_notification(booking_data, new_status)

            result = await expo_push_service.send_push_notification(
                tokens=tokens,
                title=notification["title"],
                body=notification["body"],
                data={"bookingId": str(booking_id)},
            )

            if result["invalid_tokens"]:
                await self.remove_invalid_tokens(db, result["invalid_tokens"])

            delivered = result["success"] > 0
            error_msg = None if delivered else "Failed to deliver to all devices"

            await self.save_notification_history(
                db=db,
                user_id=user_id,
                booking_id=booking_id,
                notification_type=notification["type"],
                title=notification["title"],
                body=notification["body"],
                delivered=delivered,
                error_message=error_msg,
            )

            logger.info(f"Push sent: {result['success']} success, {result['failed']} failed")
            return True

    async def _handle_booking_created(self, booking_data: dict) -> bool:
        """Handle booking_created events — fetch data from services and send email."""
        user_id_str = booking_data.get("user_id")
        booking_id_str = booking_data.get("id")
        payment_id = booking_data.get("payment_id", "")

        if not user_id_str or not booking_id_str:
            logger.error("Missing required fields in booking_created event")
            return False

        user_id = uuid.UUID(user_id_str)
        booking_id = uuid.UUID(booking_id_str)

        async with self._get_session() as db:
            # Idempotency: skip if email already sent for this payment
            if payment_id and await self._check_email_already_sent(db, payment_id):
                logger.info(f"Email already sent for payment {payment_id}, skipping")
                return True

            # Fetch data from sibling services
            user_info = await get_user_info(user_id_str)
            if not user_info or not user_info.get("email"):
                logger.warning(f"Could not get email for user {user_id_str}, skipping email")
                return True

            booking_info = await get_booking_info(booking_id_str)
            if not booking_info:
                logger.error(f"Could not fetch booking {booking_id_str}")
                return False  # Retry — booking may not be queryable yet

            payment_info = await get_payment_info(payment_id) if payment_id else None

            user_email = user_info["email"]
            user_name = user_info.get("name", "")

            # Extract payment method display from payment response
            pm_display = ""
            if payment_info and payment_info.get("paymentMethod"):
                pm_display = payment_info["paymentMethod"].get("displayLabel", "")

            # Build email from enriched data
            email_data = {
                "booking_code": booking_info.get("code", ""),
                "hotel_name": booking_info.get("hotelName", "Hotel"),
                "room_name": booking_info.get("roomName", ""),
                "check_in": booking_info.get("checkIn", ""),
                "check_out": booking_info.get("checkOut", ""),
                "guests": booking_info.get("guests", 0),
                "base_price": str(booking_info.get("basePrice", 0)),
                "tax_amount": str(booking_info.get("taxAmount", 0)),
                "service_fee": str(booking_info.get("serviceFee", 0)),
                "total_price": str(booking_info.get("totalPrice", 0)),
                "currency": booking_info.get("currency", "COP"),
                "payment_method_display": pm_display,
                "transaction_id": payment_info.get("transactionId", "") if payment_info else "",
                "user_name": user_name,
            }

            booking_code = email_data["booking_code"]
            locale = booking_info.get("locale") or "es"
            email_content = build_payment_confirmation_email(email_data, locale=locale)

            # Send email
            delivered = await email_service.send_email(
                to=user_email,
                subject=email_content["subject"],
                html_body=email_content["html"],
            )

            error_msg = None if delivered else "Failed to send email"

            # Save to notification history
            await self.save_notification_history(
                db=db,
                user_id=user_id,
                booking_id=booking_id,
                notification_type="email_payment_confirmation",
                title=email_content["subject"],
                body=f"Email de confirmacion de pago enviado a {user_email}",
                delivered=delivered,
                error_message=error_msg,
                extra_data={
                    "payment_id": payment_id,
                    "booking_code": booking_code,
                    "email": user_email,
                },
            )

            if delivered:
                logger.info(f"Payment confirmation email sent to {user_email}")
            else:
                logger.error(f"Failed to send payment confirmation email to {user_email}")

            return True

    async def process_message(self, message_body: str) -> bool:
        """Process a single SQS message by dispatching to the appropriate handler."""
        try:
            event = json.loads(message_body)
            event_type = event.get("event_type")
            entity_type = event.get("entity_type")

            if entity_type != "booking":
                logger.debug(f"Skipping non-booking event: {entity_type}")
                return True

            booking_data = event.get("data", {}).get("booking", {})

            if event_type == "booking_status_updated":
                return await self._handle_booking_status_updated(booking_data)
            elif event_type == "booking_created":
                return await self._handle_booking_created(booking_data)
            else:
                logger.debug(f"Skipping unhandled event type: {event_type}")
                return True

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False

    def poll_messages(self):
        """Poll SQS queue for messages."""
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
                return 0

            processed_count = 0
            for message in messages:
                message_body = message["Body"]
                receipt_handle = message["ReceiptHandle"]

                # Process message asynchronously
                import asyncio

                success = asyncio.run(self.process_message(message_body))

                if success:
                    self.client.delete_message(
                        QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
                    )
                    processed_count += 1
                else:
                    logger.warning("Message processing failed, will retry")

            return processed_count

        except ClientError as e:
            logger.error(f"Error polling SQS: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return 0


consumer = SQSConsumer()
