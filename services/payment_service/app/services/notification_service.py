"""Publishes typed payment events to SQS for downstream consumers (notification service, etc.)."""

import uuid

from ..models import Payment
from ..schemas import CartData, PaymentConfirmedEvent, PaymentDeclinedEvent
from .sqs_publisher import sqs_publisher


async def notify_payment_confirmed(
    payment: Payment,
    user_id: uuid.UUID,
    transaction_id: str,
    cart: CartData,
) -> None:
    """Publish a payment_confirmed event with cart data for downstream booking creation."""
    event = PaymentConfirmedEvent(
        payment_id=str(payment.id),
        user_id=str(user_id),
        amount=float(payment.amount),
        currency=payment.currency,
        transaction_id=transaction_id,
        cart=cart,
    )
    try:
        await sqs_publisher.publish_payment_confirmed(event.model_dump(by_alias=True))
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
        await sqs_publisher.publish_payment_declined(event.model_dump(by_alias=True))
    except Exception:  # noqa: B110  # nosec B110
        pass  # fire-and-forget: SQS failure must not block payment
