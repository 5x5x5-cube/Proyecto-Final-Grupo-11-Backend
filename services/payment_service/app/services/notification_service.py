"""Publishes typed payment events to SNS for downstream consumers."""

import uuid

from ..models import Payment
from ..schemas import BookingData, PaymentConfirmedEvent, PaymentDeclinedEvent
from .sns_publisher import sns_publisher


async def notify_payment_confirmed(
    payment: Payment,
    user_id: uuid.UUID,
    transaction_id: str,
    booking_snapshot: dict | None,
) -> None:
    """Publish a payment_confirmed event with booking data. Fire-and-forget."""
    booking_data = BookingData.model_validate(booking_snapshot) if booking_snapshot else None
    if not booking_data:
        return  # can't create a booking without snapshot

    event = PaymentConfirmedEvent(
        payment_id=str(payment.id),
        user_id=str(user_id),
        amount=float(payment.amount),
        currency=payment.currency,
        transaction_id=transaction_id,
        booking_data=booking_data,
    )
    try:
        await sns_publisher.publish_payment_confirmed(event.model_dump(by_alias=True))
    except Exception:  # noqa: B110  # nosec B110
        pass  # fire-and-forget: SQS failure must not block payment


async def notify_payment_declined(
    payment: Payment,
    user_id: uuid.UUID,
    error_code: str | None,
) -> None:
    """Publish a payment_declined event. Fire-and-forget."""
    event = PaymentDeclinedEvent(
        payment_id=str(payment.id),
        user_id=str(user_id),
        amount=float(payment.amount),
        currency=payment.currency,
        error_code=error_code,
    )
    try:
        await sns_publisher.publish_payment_declined(event.model_dump(by_alias=True))
    except Exception:  # noqa: B110  # nosec B110
        pass  # fire-and-forget: SQS failure must not block payment
