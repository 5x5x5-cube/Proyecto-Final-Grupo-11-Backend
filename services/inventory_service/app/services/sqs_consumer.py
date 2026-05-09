"""SQS consumer for the inventory_service (HU4.3).

Listens for ``booking.cancelled`` events emitted by booking_service and
releases the inventory for the cancelled room+dates so other travelers can
book it again.

The consumer follows the same shape as ``booking_service.sqs_consumer``:
``boto3`` client, JSON parsing, dispatch by ``event_type``. Only events
relevant to inventory are handled — anything else is logged and ignored.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date

import boto3

from ..config import settings
from ..database import async_session_factory
from .availability_service import release_dates

logger = logging.getLogger(__name__)


def _parse_iso_date(value: str | None) -> date | None:
    """Best-effort ISO date parser. Returns None on bad input so we can
    log and skip rather than crashing the consumer loop."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class SQSConsumer:
    """Inventory-side consumer of SNS→SQS events."""

    def __init__(self):
        client_kwargs: dict = {"region_name": settings.aws_region}
        if settings.aws_access_key_id and settings.aws_access_key_id != "test":
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url
        self.client = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.sqs_queue_url

    # ── Event dispatch ────────────────────────────────────────────────

    async def process_message(self, message_body: str) -> bool:
        """Parse and dispatch a single SQS message.

        Returns True when the message was handled (or safely ignored) and
        can be deleted from the queue. False signals a transient failure
        the queue should retry.
        """
        try:
            event = json.loads(message_body)
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in SQS message: %s", exc)
            return False

        event_type = event.get("event_type")
        entity_type = event.get("entity_type")

        if entity_type != "booking":
            logger.debug("Ignoring non-booking event: entity_type=%s", entity_type)
            return True

        if event_type == "booking.cancelled":
            booking_data = event.get("data", {}).get("booking", {})
            return await self._handle_booking_cancelled(booking_data)

        logger.debug("Ignoring unhandled event type: %s", event_type)
        return True

    # ── Handlers ──────────────────────────────────────────────────────

    async def _handle_booking_cancelled(self, booking_data: dict) -> bool:
        """Release the room+dates pinned by the cancelled booking (CA6).

        Note on idempotency: re-delivering the same SQS message would
        increment availability twice. ``release_dates`` already caps at
        ``total_quantity`` so the worst case is a no-op; we still log to
        surface duplicates during ops review.
        """
        room_id_raw = booking_data.get("room_id")
        check_in_raw = booking_data.get("check_in")
        check_out_raw = booking_data.get("check_out")
        booking_id = booking_data.get("id")

        if not room_id_raw or not check_in_raw or not check_out_raw:
            logger.error("booking.cancelled missing required fields (booking_id=%s)", booking_id)
            return False

        try:
            room_id = uuid.UUID(room_id_raw)
        except ValueError:
            logger.error("Invalid room_id in booking.cancelled: %s", room_id_raw)
            return False

        check_in = _parse_iso_date(check_in_raw)
        check_out = _parse_iso_date(check_out_raw)
        if check_in is None or check_out is None:
            logger.error(
                "Invalid date(s) in booking.cancelled: check_in=%s check_out=%s",
                check_in_raw,
                check_out_raw,
            )
            return False

        async with async_session_factory() as session:
            try:
                await release_dates(session, room_id, check_in, check_out)
                await session.commit()
            except Exception as exc:  # noqa: BLE001 — surface to SQS retry loop
                logger.exception("Failed to release inventory for booking %s: %s", booking_id, exc)
                await session.rollback()
                return False

        logger.info(
            "Released inventory for cancelled booking %s (room=%s, %s → %s)",
            booking_id,
            room_id,
            check_in,
            check_out,
        )
        return True


sqs_consumer = SQSConsumer()
