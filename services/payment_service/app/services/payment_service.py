import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..models import Payment, PaymentToken
from ..schemas import InitiatePaymentRequest, PaymentResponse, TokenizeRequest, TokenizeResponse
from . import booking_client, payment_adapter, token_service
from .sqs_publisher import sqs_publisher


async def tokenize_card(db: AsyncSession, request: TokenizeRequest) -> TokenizeResponse:
    """Tokenize a card for later payment use."""
    token = await token_service.create_token(
        db=db,
        card_number=request.card_number,
        card_holder=request.card_holder,
        expiry=request.expiry,
        cvv=request.cvv,
    )
    return TokenizeResponse(
        token=token.token,
        card_last4=token.card_last4,
        card_brand=token.card_brand,
        expires_at=token.expires_at,
    )


async def initiate_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: InitiatePaymentRequest,
) -> PaymentResponse:
    """Orchestrate the full payment flow."""
    # 1. Validate token
    result = await db.execute(select(PaymentToken).where(PaymentToken.token == request.token))
    token = result.scalar_one_or_none()
    if not token:
        raise InvalidTokenError("Payment token not found")

    now = datetime.now(timezone.utc)
    if token.expires_at.replace(tzinfo=timezone.utc) < now:
        raise TokenExpiredError()

    # 2. Create Payment record
    payment = Payment(
        id=uuid.uuid4(),
        booking_id=request.booking_id,
        user_id=user_id,
        amount=request.amount,
        currency=request.currency,
        method=request.method,
        status="processing",
        token_id=token.id,
        card_last4=token.card_last4,
        card_brand=token.card_brand,
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # 3. Call payment adapter
    gateway_result = await payment_adapter.process_payment(
        card_number_hash=token.card_number_hash,
        amount=request.amount,
    )

    payment.transaction_id = gateway_result.transaction_id
    payment.processed_at = datetime.now(timezone.utc)

    if gateway_result.approved:
        payment.status = "approved"

        # 4. Publish SQS event (fire-and-forget)
        try:
            await sqs_publisher.publish_payment_confirmed(
                {
                    "payment_id": str(payment.id),
                    "booking_id": str(payment.booking_id),
                    "user_id": str(user_id),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "transaction_id": gateway_result.transaction_id,
                }
            )
        except Exception:  # noqa: B110  # nosec B110
            pass  # fire-and-forget: SQS failure must not block payment

        message = "Payment approved"
    else:
        payment.status = "declined"
        payment.error_code = gateway_result.error_code

        # Publish decline event (fire-and-forget)
        try:
            await sqs_publisher.publish_payment_declined(
                {
                    "payment_id": str(payment.id),
                    "booking_id": str(payment.booking_id),
                    "user_id": str(user_id),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "error_code": gateway_result.error_code,
                }
            )
        except Exception:  # noqa: B110  # nosec B110
            pass  # fire-and-forget: SQS failure must not block payment

        message = "Payment declined"

    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        booking_id=payment.booking_id,
        booking_code=payment.booking_code,
        amount=float(payment.amount),
        currency=payment.currency,
        method=payment.method,
        card_last4=payment.card_last4,
        card_brand=payment.card_brand,
        transaction_id=payment.transaction_id,
        message=message,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> PaymentResponse:
    """Retrieve a payment by its ID."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise PaymentNotFoundError(str(payment_id))

    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        booking_id=payment.booking_id,
        booking_code=payment.booking_code,
        amount=float(payment.amount),
        currency=payment.currency,
        method=payment.method,
        card_last4=payment.card_last4,
        card_brand=payment.card_brand,
        transaction_id=payment.transaction_id,
        message=None,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
