import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..exceptions import (
    InvalidTokenError,
    PaymentNotFoundError,
    PaymentNotRefundableError,
    RefundAmountInvalidError,
    TokenExpiredError,
)
from ..models import ExchangeRate, FraudAlert, Payment, PaymentToken, UserPaymentMethod
from ..redis_client import get_redis
from ..schemas import (
    InitiatePaymentRequest,
    PaymentAdminListItem,
    PaymentAdminListResponse,
    PaymentAdminSummary,
    PaymentConfirmationWebhook,
    PaymentMethodResponse,
    PaymentResponse,
    RefundResponse,
)
from . import cart_client, payment_adapter
from .fraud_detector import evaluate_transaction, record_transaction
from .notification_service import notify_payment_confirmed, notify_payment_declined
from .sns_publisher import sns_publisher


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
        message=message,
        created_at=payment.created_at,
        processed_at=payment.processed_at,
    )


async def initiate_payment(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: InitiatePaymentRequest,
    locale: str = "es",
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
    cop_total = float(cart.price_breakdown.total)
    cop_base = float(cart.price_breakdown.subtotal)
    cop_tax = float(cart.price_breakdown.vat)
    cop_fee = float(cart.price_breakdown.service_fee)
    target_currency = request.currency.upper()

    # Convert to target currency if different from COP
    if target_currency != "COP":
        rate_result = await db.execute(
            select(ExchangeRate).where(ExchangeRate.currency == target_currency)
        )
        rate_row = rate_result.scalar_one_or_none()
        if rate_row:
            rate = float(rate_row.rate)
            total_price = round(cop_total * rate, rate_row.decimals)
            base_price = round(cop_base * rate, rate_row.decimals)
            tax_amount = round(cop_tax * rate, rate_row.decimals)
            service_fee = round(cop_fee * rate, rate_row.decimals)
            currency = target_currency
        else:
            # Unknown currency — fall back to COP
            total_price = cop_total
            base_price = cop_base
            tax_amount = cop_tax
            service_fee = cop_fee
            currency = "COP"
    else:
        total_price = cop_total
        base_price = cop_base
        tax_amount = cop_tax
        service_fee = cop_fee
        currency = "COP"

    # Snapshot the booking data — in the target currency
    booking_snapshot = {
        "roomId": cart.room_id,
        "hotelId": cart.hotel_id,
        "holdId": cart.hold_id,
        "checkIn": cart.check_in,
        "checkOut": cart.check_out,
        "guests": cart.guests,
        "basePrice": str(base_price),
        "taxAmount": str(tax_amount),
        "serviceFee": str(service_fee),
        "totalPrice": str(total_price),
        "locale": locale,
    }

    payment = Payment(
        id=uuid.uuid4(),
        user_id=user_id,
        payment_method_id=payment_method.id,
        cart_id=uuid.UUID(cart.id),
        booking_snapshot=booking_snapshot,
        amount=total_price,
        currency=currency,
        status="processing",
        created_at=datetime.now(timezone.utc),
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    await db.refresh(payment_method)

    # 5. Fraud detection (HU4.7) — runs before the gateway call so suspicious
    #    transactions never reach the processor. State lives in Redis so the
    #    check is fast (one or two ZSET ops + one GET).
    redis = await get_redis()
    fraud_result = await evaluate_transaction(
        redis, user_id, float(payment.amount), payment_method.id
    )
    if fraud_result is not None:
        return await _block_payment_for_fraud(
            db=db,
            payment=payment,
            payment_method=payment_method,
            fraud_result=fraud_result,
        )

    # Clean transaction — record it in Redis so future duplicate/velocity
    # checks see it, then continue with the normal gateway flow.
    await record_transaction(redis, user_id, float(payment.amount), payment_method.id)

    # 6. Submit to gateway for async processing (HTTP call, returns immediately)
    webhook_url = f"{settings.payment_service_url}/api/v1/payments/{payment.id}/confirmation"

    await payment_adapter.submit_to_gateway(
        payment_id=payment.id,
        token=token.token,
        amount=float(payment.amount),
        currency=payment.currency,
        webhook_url=webhook_url,
    )

    return _build_payment_response(payment, payment_method)


async def _block_payment_for_fraud(
    db: AsyncSession,
    payment: Payment,
    payment_method: UserPaymentMethod,
    fraud_result,
) -> PaymentResponse:
    """Mark the payment as blocked, persist a FraudAlert row and publish the
    fraud_detected event. Gateway is *not* invoked.

    The SNS publish is fire-and-forget: a downstream failure must not undo the
    block (the payment is already safely in `blocked_fraud_review`).
    """
    alert = FraudAlert(
        id=uuid.uuid4(),
        payment_id=payment.id,
        user_id=payment.user_id,
        alert_type=fraud_result.alert_type,
        severity=fraud_result.severity,
        triggered_reason=fraud_result.triggered_reason,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(alert)
    payment.status = "blocked_fraud_review"
    await db.commit()
    await db.refresh(payment)
    await db.refresh(alert)

    try:
        await sns_publisher.publish_fraud_detected(
            {
                "alert_id": str(alert.id),
                "payment_id": str(payment.id),
                "user_id": str(payment.user_id),
                "amount": float(payment.amount),
                "currency": payment.currency,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "triggered_reason": alert.triggered_reason,
            }
        )
    except Exception:  # noqa: BLE001 — fire-and-forget; do not roll back the block
        pass

    return _build_payment_response(
        payment, payment_method, message=f"Blocked by fraud rule: {alert.alert_type}"
    )


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
        await notify_payment_confirmed(
            payment, payment.user_id, webhook.transaction_id, payment.booking_snapshot
        )
    else:
        payment.status = "declined"
        payment.error_code = webhook.error_code
        await notify_payment_declined(payment, payment.user_id, webhook.error_code)

    await db.commit()


async def list_payments(
    db: AsyncSession,
    *,
    status: str | None = None,
    method: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PaymentAdminListResponse:
    """Admin: list payments with filters and pagination.

    Joins UserPaymentMethod so we can filter by method type and surface the
    human-readable method label (e.g. "Visa •••• 4242") in a single round-trip.
    """
    conditions = []
    if status:
        conditions.append(Payment.status == status)
    if method:
        conditions.append(UserPaymentMethod.method_type == method)
    if date_from is not None:
        conditions.append(Payment.created_at >= date_from)
    if date_to is not None:
        conditions.append(Payment.created_at <= date_to)
    if amount_min is not None:
        conditions.append(Payment.amount >= amount_min)
    if amount_max is not None:
        conditions.append(Payment.amount <= amount_max)

    base_select = select(Payment, UserPaymentMethod).join(
        UserPaymentMethod, Payment.payment_method_id == UserPaymentMethod.id
    )
    count_select = select(func.count(Payment.id)).join(
        UserPaymentMethod, Payment.payment_method_id == UserPaymentMethod.id
    )
    if conditions:
        where_clause = and_(*conditions)
        base_select = base_select.where(where_clause)
        count_select = count_select.where(where_clause)

    total_result = await db.execute(count_select)
    total = total_result.scalar() or 0

    paged = (
        base_select.order_by(Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(paged)).all()

    items = [
        PaymentAdminListItem(
            id=p.id,
            user_id=p.user_id,
            amount=float(p.amount),
            currency=p.currency,
            method=pm.method_type,
            method_label=pm.display_label,
            status=p.status,
            transaction_id=p.transaction_id,
            error_code=p.error_code,
            created_at=p.created_at,
            processed_at=p.processed_at,
        )
        for p, pm in rows
    ]
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaymentAdminListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


async def get_payments_summary(
    db: AsyncSession,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> PaymentAdminSummary:
    """Aggregate payment counts and amounts grouped by status over a date window.

    Single round-trip: GROUP BY status returning (status, count, sum). The
    approval rate is approved / (approved + declined) — payments still in
    `processing` are excluded from the denominator because they have not
    been decided yet.
    """
    conditions: list = []
    if date_from is not None:
        conditions.append(Payment.created_at >= date_from)
    if date_to is not None:
        conditions.append(Payment.created_at <= date_to)

    q = select(
        Payment.status,
        func.count(Payment.id).label("count"),
        func.coalesce(func.sum(Payment.amount), 0).label("amount"),
    )
    if conditions:
        q = q.where(and_(*conditions))
    q = q.group_by(Payment.status)

    rows = (await db.execute(q)).all()
    by_status: dict[str, tuple[int, float]] = {
        row.status: (int(row.count), float(row.amount)) for row in rows
    }

    approved_count, total_processed = by_status.get("approved", (0, 0.0))
    declined_count, total_declined = by_status.get("declined", (0, 0.0))
    refunded_count, total_refunded = by_status.get("refunded", (0, 0.0))
    processing_count, _ = by_status.get("processing", (0, 0.0))

    decided = approved_count + declined_count
    approval_rate = (approved_count / decided) if decided > 0 else 0.0

    transaction_count = approved_count + declined_count + refunded_count + processing_count

    return PaymentAdminSummary(
        total_processed=total_processed,
        total_declined=total_declined,
        total_refunded=total_refunded,
        approval_rate=approval_rate,
        transaction_count=transaction_count,
        approved_count=approved_count,
        declined_count=declined_count,
        refunded_count=refunded_count,
        processing_count=processing_count,
        currency="COP",
    )


async def export_payments_csv(
    db: AsyncSession,
    *,
    status: str | None = None,
    method: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
) -> str:
    """Render filtered payments as a CSV string. Same filters as list_payments
    but no pagination — the caller exports all matching rows.

    Returns a fully-rendered CSV. For very large exports this could be
    converted to a streaming generator; today's volume does not justify it.
    """
    conditions: list = []
    if status:
        conditions.append(Payment.status == status)
    if method:
        conditions.append(UserPaymentMethod.method_type == method)
    if date_from is not None:
        conditions.append(Payment.created_at >= date_from)
    if date_to is not None:
        conditions.append(Payment.created_at <= date_to)
    if amount_min is not None:
        conditions.append(Payment.amount >= amount_min)
    if amount_max is not None:
        conditions.append(Payment.amount <= amount_max)

    q = select(Payment, UserPaymentMethod).join(
        UserPaymentMethod, Payment.payment_method_id == UserPaymentMethod.id
    )
    if conditions:
        q = q.where(and_(*conditions))
    q = q.order_by(Payment.created_at.desc())

    rows = (await db.execute(q)).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "user_id",
            "amount",
            "currency",
            "method",
            "method_label",
            "status",
            "transaction_id",
            "error_code",
            "created_at",
            "processed_at",
        ]
    )
    for p, pm in rows:
        writer.writerow(
            [
                str(p.id),
                str(p.user_id),
                float(p.amount),
                p.currency,
                pm.method_type,
                pm.display_label,
                p.status,
                p.transaction_id or "",
                p.error_code or "",
                p.created_at.isoformat() if p.created_at else "",
                p.processed_at.isoformat() if p.processed_at else "",
            ]
        )
    return buffer.getvalue()


async def refund_payment(
    db: AsyncSession,
    payment_id: uuid.UUID,
    amount: float,
    reason: str | None = None,
) -> RefundResponse:
    """Mark an approved payment as refunded for the given amount.

    HU4.3 — refunds are only allowed against payments that were approved.
    Already-refunded, declined or processing payments are rejected. The
    requested amount must be a positive number not greater than the original.

    Real-world refunds would also call out to the gateway adapter; that part
    is intentionally left for later (the gateway interaction is out of scope
    for this story — we record the state transition only).
    """
    if amount <= 0:
        raise RefundAmountInvalidError("Refund amount must be greater than zero")

    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise PaymentNotFoundError(str(payment_id))

    if payment.status != "approved":
        raise PaymentNotRefundableError(payment.status)

    if amount > float(payment.amount):
        raise RefundAmountInvalidError(
            f"Refund amount {amount} exceeds original payment amount {payment.amount}"
        )

    now = datetime.now(timezone.utc)
    payment.status = "refunded"
    payment.refund_amount = amount
    payment.refunded_at = now
    await db.commit()
    await db.refresh(payment)

    return RefundResponse(
        payment_id=payment.id,
        status=payment.status,
        amount=float(payment.amount),
        currency=payment.currency,
        refund_amount=float(payment.refund_amount or 0),
        refunded_at=payment.refunded_at or now,
        reason=reason,
    )


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
