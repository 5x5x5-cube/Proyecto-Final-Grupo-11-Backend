import json
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import AsyncSessionLocal
from ..models import NotificationHistory, PushToken
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

    async def process_message(self, message_body: str) -> bool:
        """Process a single SQS message."""
        try:
            event = json.loads(message_body)
            event_type = event.get("event_type")
            entity_type = event.get("entity_type")

            if entity_type != "booking":
                logger.debug(f"Skipping non-booking event: {entity_type}")
                return True  # Not an error, just not for us

            if event_type != "booking_status_updated":
                logger.debug(f"Skipping non-status-update event: {event_type}")
                return True

            booking_data = event.get("data", {}).get("booking", {})
            user_id_str = booking_data.get("user_id")
            booking_id_str = booking_data.get("id")
            new_status = booking_data.get("status")

            if not user_id_str or not booking_id_str or not new_status:
                logger.error("Missing required fields in booking event")
                return False

            user_id = uuid.UUID(user_id_str)
            booking_id = uuid.UUID(booking_id_str)

            async with AsyncSessionLocal() as db:
                # Get user's push tokens
                tokens = await self.get_user_push_tokens(db, user_id)

                if not tokens:
                    logger.info(f"No push tokens found for user {user_id}")
                    return True  # Not an error

                # Build notification
                notification = build_booking_notification(booking_data, new_status)

                # Send push notification
                result = await expo_push_service.send_push_notification(
                    tokens=tokens,
                    title=notification["title"],
                    body=notification["body"],
                    data={"bookingId": str(booking_id)},
                )

                # Remove invalid tokens
                if result["invalid_tokens"]:
                    await self.remove_invalid_tokens(db, result["invalid_tokens"])

                # Save to history
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

                logger.info(
                    f"Notification sent: {result['success']} success, {result['failed']} failed"
                )
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
