import logging
from typing import Any, Dict, List

from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)

from ..config import settings

logger = logging.getLogger(__name__)


class ExpoPushService:
    def __init__(self):
        self.client = PushClient()

    async def send_push_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Send push notification to multiple Expo push tokens.

        Returns:
            Dict with 'success' count, 'failed' count, and 'invalid_tokens' list
        """
        if not tokens:
            return {"success": 0, "failed": 0, "invalid_tokens": []}

        messages = []
        for token in tokens:
            if not PushClient.is_exponent_push_token(token):
                logger.warning(f"Invalid Expo push token format: {token}")
                continue

            messages.append(
                PushMessage(
                    to=token,
                    title=title,
                    body=body,
                    data=data or {},
                    sound="default",
                    badge=1,
                    priority="high",
                )
            )

        if not messages:
            return {"success": 0, "failed": 0, "invalid_tokens": tokens}

        try:
            # Send messages in chunks of 100 (Expo limit)
            chunk_size = 100
            all_tickets = []
            invalid_tokens = []

            for i in range(0, len(messages), chunk_size):
                chunk = messages[i : i + chunk_size]
                try:
                    tickets = self.client.publish_multiple(chunk)
                    all_tickets.extend(tickets)
                except PushServerError as e:
                    logger.error(f"Expo push server error: {e}")
                    return {"success": 0, "failed": len(chunk), "invalid_tokens": []}

            # Process tickets
            success_count = 0
            failed_count = 0

            for i, ticket in enumerate(all_tickets):
                if ticket.is_success():
                    success_count += 1
                else:
                    failed_count += 1
                    token = messages[i].to

                    # Check if token is invalid/unregistered
                    if isinstance(ticket.message, str):
                        if "DeviceNotRegistered" in ticket.message:
                            invalid_tokens.append(token)
                            logger.warning(f"Device not registered: {token}")
                        else:
                            logger.error(f"Push notification failed: {ticket.message}")

            return {
                "success": success_count,
                "failed": failed_count,
                "invalid_tokens": invalid_tokens,
            }

        except Exception as e:
            logger.error(f"Unexpected error sending push notifications: {e}")
            return {"success": 0, "failed": len(messages), "invalid_tokens": []}


expo_push_service = ExpoPushService()
