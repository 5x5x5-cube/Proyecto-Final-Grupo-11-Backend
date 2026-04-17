import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..models import Payment, PaymentMethod, PaymentToken
from ..schemas import (
    InitiatePaymentRequest,
    PaymentResponse,
    TokenizeCardRequest,
    TokenizeRequest,
    TokenizeResponse,
    TokenizeTransferRequest,
    TokenizeWalletRequest,
)
from . import cart_client, payment_adapter, token_service
from .notification_service import notify_payment_confirmed, notify_payment_declined


def _parse_tokenize_request(body: dict) -> TokenizeRequest:
    """Parse and validate a tokenize request body using the discriminated union."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(TokenizeRequest)
    return adapter.validate_python(body)


async def tokenize_method(db: AsyncSession, body: dict) -> TokenizeResponse:
    """Tokenize any payment method (card, wallet, or transfer)."""
    method = body.get("method", "credit_card")
    if method not in PaymentMethod._value2member_map_:
        raise InvalidTokenError(f"Unsupported payment method: {method}")

    request = _parse_tokenize_request(body)

    if isinstance(request, TokenizeCardRequest):
        token = await token_service.create_card_token(
            db=db,
            method=request.method,
            card_number=request.card_number,
            card_holder=request.card_holder,
            expiry=request.expiry,
            cvv=request.cvv,
        )
    elif isinstance(request, TokenizeWalletRequest):
        token = await token_service.create_wallet_token(
            db=db,
            wallet_provider=request.wallet_provider,
            wallet_email=request.wallet_email,
        )
    elif isinstance(request, TokenizeTransferRequest):
        token = await token_service.create_transfer_token(
            db=db,
            bank_code=request.bank_code,
            account_number=request.account_number,
            account_holder=request.account_holder,
        )
    else:
        raise InvalidTokenError("Unsupported payment method")

    return TokenizeResponse(
        token=token.token,
        method=token.method,
        display_label=token.display_label,
        expires_at=token.expires_at,
        card_last4=token.method_data.get("last4"),
        card_brand=token.method_data.get("brand"),
        wallet_provider=token.method_data.get("provider"),
        bank_code=token.method_data.get("bankCode"),
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

    # 2. Fetch cart data
    cart = await cart_client.get_cart(cart_id=request.cart_id, user_id=user_id)

    # 3. Create Payment record (no booking_id yet — created after approval)
    total_price = float(cart.price_breakdown.total)
    currency = cart.price_breakdown.currency

    payment = Payment(
        id=uuid.uuid4(),
        user_id=user_id,
        amount=total_price,
        currency=currency,
        method=request.method,
        status="processing",
        token_id=token.id,
        display_label=token.display_label,
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    # 4. Call payment adapter
    card_hash = token.method_data.get("numberHash") if token.method_data else None
    gateway_result = await payment_adapter.process_payment(
        card_number_hash=card_hash,
        amount=total_price,
    )

    payment.transaction_id = gateway_result.transaction_id
    payment.processed_at = datetime.now(timezone.utc)

    if gateway_result.approved:
        payment.status = "approved"

        # 5. Publish to SQS — a downstream consumer (PaymentConfirmation)
        # will create the booking and notify the user
        await notify_payment_confirmed(payment, user_id, gateway_result.transaction_id, cart)

        message = "Payment approved"
    else:
        payment.status = "declined"
        payment.error_code = gateway_result.error_code

        await notify_payment_declined(payment, user_id, gateway_result.error_code)

        message = "Payment declined"

    await db.commit()
    await db.refresh(payment)

    card_last4 = token.method_data.get("last4") if token.method_data else None
    card_brand = token.method_data.get("brand") if token.method_data else None

    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        booking_id=payment.booking_id,
        booking_code=payment.booking_code,
        amount=float(payment.amount),
        currency=payment.currency,
        method=payment.method,
        card_last4=card_last4,
        card_brand=card_brand,
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

    # Get token for display data
    token_result = await db.execute(select(PaymentToken).where(PaymentToken.id == payment.token_id))
    token = token_result.scalar_one_or_none()
    card_last4 = token.method_data.get("last4") if token and token.method_data else None
    card_brand = token.method_data.get("brand") if token and token.method_data else None

    return PaymentResponse(
        payment_id=payment.id,
        status=payment.status,
        booking_id=payment.booking_id,
        booking_code=payment.booking_code,
        amount=float(payment.amount),
        currency=payment.currency,
        method=payment.method,
        card_last4=card_last4,
        card_brand=card_brand,
        transaction_id=payment.transaction_id,
        message=None,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )
