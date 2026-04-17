import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..models import Payment, PaymentToken, UserPaymentMethod
from ..schemas import (
    InitiatePaymentRequest,
    PaymentConfirmationWebhook,
    PaymentMethodResponse,
    PaymentResponse,
)
from . import cart_client, payment_adapter
from .notification_service import notify_payment_confirmed, notify_payment_declined


def _build_method_response(pm: UserPaymentMethod) -> PaymentMethodResponse:
    return PaymentMethodResponse(
        id=pm.id,
        method_type=pm.method_type,
        display_label=pm.display_label,
        card_last4=pm.card_last4,
        card_brand=pm.card_brand,
    )


def _build_payment_response(
    payment: Payment, pm: UserPaymentMethod | None, message: str | None = None
) -> PaymentResponse:
    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        payment_method=_build_method_response(pm) if pm else None,
        amount=float(payment.amount),
        currency=payment.currency,
        transaction_id=payment.transaction_id,
        booking_id=payment.booking_id,
        booking_code=payment.booking_code,
        message=message,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


async def initiate_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: InitiatePaymentRequest,
) -> PaymentResponse:
    """Validate token/cart, save payment method, create payment, fire gateway."""
    # 1. Validate token with the gateway (simulated: query PaymentToken)
    result = await db.execute(select(PaymentToken).where(PaymentToken.token == request.token))
    token = result.scalar_one_or_none()
    if not token:
        raise InvalidTokenError("Payment token not found")

    now = datetime.now(timezone.utc)
    if token.expires_at.replace(tzinfo=timezone.utc) < now:
        raise TokenExpiredError()

    # 2. Fetch and validate cart
    cart = await cart_client.get_cart(cart_id=request.cart_id, user_id=user_id)

    # 3. Save the user's payment method from tokenize response data
    card_last4 = token.method_data.get("last4") if token.method_data else None
    card_brand = token.method_data.get("brand") if token.method_data else None

    payment_method = UserPaymentMethod(
        id=uuid.uuid4(),
        user_id=user_id,
        gateway_token=token.token,
        method_type=request.method,
        display_label=token.display_label,
        card_last4=card_last4,
        card_brand=card_brand,
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment_method)
    await db.flush()  # ensure FK is available before Payment insert

    # 4. Create Payment linked to the payment method
    total_price = float(cart.price_breakdown.total)
    currency = cart.price_breakdown.currency

    payment = Payment(
        id=uuid.uuid4(),
        user_id=user_id,
        payment_method_id=payment_method.id,
        amount=total_price,
        currency=currency,
        status="processing",
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    await db.refresh(payment_method)

    # 5. Fire gateway adapter in background
    card_hash = token.method_data.get("numberHash") if token.method_data else None
    webhook_url = f"{settings.payment_service_url}/api/v1/payments/{payment.id}/confirmation"

    asyncio.create_task(
        payment_adapter.process_payment_async(
            payment_id=payment.id,
            card_number_hash=card_hash,
            webhook_url=webhook_url,
        )
    )

    return _build_payment_response(payment, payment_method)


async def confirm_payment(
    db: AsyncSession,
    webhook: PaymentConfirmationWebhook,
) -> None:
    """Handle the gateway webhook callback — update payment status and notify."""
    result = await db.execute(select(Payment).where(Payment.id == webhook.payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        return

    if payment.status != "processing":
        return

    payment.transaction_id = webhook.transaction_id
    payment.processed_at = datetime.now(timezone.utc)

    if webhook.approved:
        payment.status = "approved"
        await notify_payment_confirmed(payment, payment.user_id, webhook.transaction_id)
    else:
        payment.status = "declined"
        payment.error_code = webhook.error_code
        await notify_payment_declined(payment, payment.user_id, webhook.error_code)

    await db.commit()


async def get_payment(db: AsyncSession, payment_id: uuid.UUID) -> PaymentResponse:
    """Retrieve a payment with its associated payment method."""
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise PaymentNotFoundError(str(payment_id))

    # Load the user's payment method for display data
    pm_result = await db.execute(
        select(UserPaymentMethod).where(UserPaymentMethod.id == payment.payment_method_id)
    )
    pm = pm_result.scalar_one_or_none()

    message = None
    if payment.status == "approved":
        message = "Payment approved"
    elif payment.status == "declined":
        message = "Payment declined"

    return _build_payment_response(payment, pm, message)
