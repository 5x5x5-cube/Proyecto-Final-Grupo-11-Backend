"""Payment service endpoints — our domain."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import (
    FraudAlertAlreadyReviewedError,
    FraudAlertNotFoundError,
    InvalidTokenError,
    PaymentNotFoundError,
    PaymentNotRefundableError,
    RefundAmountInvalidError,
    TokenExpiredError,
)
from ..models import ExchangeRate
from ..schemas import (
    ExchangeRateResponse,
    FraudAlertItem,
    FraudAlertListResponse,
    FraudAlertReviewRequest,
    FraudAlertSummary,
    InitiatePaymentRequest,
    PaymentAdminListResponse,
    PaymentAdminSummary,
    PaymentConfirmationWebhook,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
)
from ..services.cart_client import CartExpiredError, CartNotFoundError
from ..services.payment_service import confirm_payment
from ..services.payment_service import export_payments_csv as export_payments_csv_svc
from ..services.payment_service import get_fraud_alerts_summary as get_fraud_alerts_summary_svc
from ..services.payment_service import get_payment as get_payment_svc
from ..services.payment_service import get_payments_summary as get_payments_summary_svc
from ..services.payment_service import initiate_payment
from ..services.payment_service import list_fraud_alerts as list_fraud_alerts_svc
from ..services.payment_service import list_payments as list_payments_svc
from ..services.payment_service import refund_payment as refund_payment_svc
from ..services.payment_service import review_fraud_alert as review_fraud_alert_svc

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def get_user_id(request: Request) -> uuid.UUID:
    """Extract and validate the X-User-Id header (resolved by auth service from JWT)."""
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid X-User-Id header")


@router.post("/initiate", response_model=PaymentResponse, status_code=202)
async def initiate_payment_endpoint(
    request: InitiatePaymentRequest,
    raw_request: Request,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a payment. Tokenizes via gateway, saves payment method, fires adapter.

    Returns 202 immediately; client polls GET /{id} for result.
    """
    accept_lang = raw_request.headers.get("accept-language", "es")
    locale = "en" if accept_lang.startswith("en") else "es"
    try:
        return await initiate_payment(db=db, user_id=user_id, request=request, locale=locale)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TokenExpiredError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except CartNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CartExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc))


@router.post("/{payment_id}/confirmation", status_code=200)
async def payment_confirmation_webhook(
    payment_id: uuid.UUID,
    webhook: PaymentConfirmationWebhook,
    db: AsyncSession = Depends(get_db),
):
    """Webhook called by the Payment Adapter after processing.

    Internal endpoint — not called by clients.
    """
    if webhook.payment_id != payment_id:
        raise HTTPException(status_code=400, detail="Payment ID mismatch")

    await confirm_payment(db=db, webhook=webhook)
    return {"status": "received"}


@router.get("/exchange-rates", response_model=List[ExchangeRateResponse])
async def get_exchange_rates(db: AsyncSession = Depends(get_db)):
    """Return current exchange rates (COP base). Public, cacheable."""
    result = await db.execute(select(ExchangeRate))
    return result.scalars().all()


@router.get("", response_model=PaymentAdminListResponse)
async def list_payments_endpoint(
    status: str | None = Query(None),
    method: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    amount_min: float | None = Query(None, alias="amountMin"),
    amount_max: float | None = Query(None, alias="amountMax"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list payments with filters and pagination.

    Query params (all optional):
      - status: approved | declined | processing | refunded
      - method: credit_card | debit_card | digital_wallet | transfer
      - dateFrom, dateTo: ISO datetimes filtering by Payment.created_at
      - amountMin, amountMax: numeric bounds on Payment.amount
      - page (>=1), pageSize (1-100)
    """
    return await list_payments_svc(
        db=db,
        status=status,
        method=method,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=PaymentAdminSummary)
async def payments_summary_endpoint(
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    db: AsyncSession = Depends(get_db),
):
    """Admin: aggregated payment metrics for a date window.

    Returns counts and amounts per status plus the approval rate
    (approved / decided). Used by the dashboard summary cards.
    """
    return await get_payments_summary_svc(db=db, date_from=date_from, date_to=date_to)


@router.get("/export")
async def export_payments_endpoint(
    format: str = Query("csv"),
    status: str | None = Query(None),
    method: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    amount_min: float | None = Query(None, alias="amountMin"),
    amount_max: float | None = Query(None, alias="amountMax"),
    db: AsyncSession = Depends(get_db),
):
    """Admin: export filtered payments as a downloadable CSV.

    Accepts the same filters as the listing endpoint but skips pagination
    so the export covers every matching row. Only `format=csv` is supported
    today; other formats return 400.
    """
    if format != "csv":
        raise HTTPException(status_code=400, detail="Only CSV format is supported")

    csv_data = await export_payments_csv_svc(
        db=db,
        status=status,
        method=method,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
    )


# ─── Fraud alerts admin endpoints (HU4.7) ───────────────────────────────────


@router.get("/fraud-alerts/summary", response_model=FraudAlertSummary)
async def fraud_alerts_summary_endpoint(
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated fraud-alert metrics for the admin dashboard."""
    return await get_fraud_alerts_summary_svc(db=db, date_from=date_from, date_to=date_to)


@router.get("/fraud-alerts", response_model=FraudAlertListResponse)
async def list_fraud_alerts_endpoint(
    alert_type: str | None = Query(None, alias="alertType"),
    status: str | None = Query(None),
    date_from: datetime | None = Query(None, alias="dateFrom"),
    date_to: datetime | None = Query(None, alias="dateTo"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, alias="pageSize", ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Admin: list fraud alerts with filters and pagination.

    Query params (all optional):
      - alertType: duplicate | velocity | threed_secure_failed
      - status: pending | approved | confirmed_block
      - dateFrom, dateTo: ISO datetimes filtering by FraudAlert.created_at
      - page (>=1), pageSize (1-100)
    """
    return await list_fraud_alerts_svc(
        db=db,
        alert_type=alert_type,
        status=status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.post("/fraud-alerts/{alert_id}/review", response_model=FraudAlertItem)
async def review_fraud_alert_endpoint(
    alert_id: uuid.UUID,
    request: FraudAlertReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """Admin manual review of a pending alert (HU4.7 CA6).

    `action=approve` → alert marked approved AND linked payment is moved
    back to 'processing' so the user can retry. (Note: the gateway token
    likely expired, so the user must re-initiate from the cart.)

    `action=confirm_block` → alert marked confirmed_block, payment stays
    in 'blocked_fraud_review'.

    Re-reviewing an already-decided alert returns 409.
    """
    try:
        return await review_fraud_alert_svc(db=db, alert_id=alert_id, request=request)
    except FraudAlertNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FraudAlertAlreadyReviewedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{payment_id}/refund", response_model=RefundResponse, status_code=200)
async def refund_payment_endpoint(
    payment_id: uuid.UUID,
    request: RefundRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refund an approved payment for the given amount (HU4.3).

    Internal endpoint — invoked by booking_service after applying the
    cancellation policy. The amount is computed by the caller (100% / 50% /
    0%) so this endpoint stays policy-agnostic.

    Errors:
    - 404 if the payment does not exist
    - 400 if the payment is not in approved state
    - 400 if the requested amount is invalid (<= 0 or > original)
    """
    try:
        return await refund_payment_svc(
            db=db,
            payment_id=payment_id,
            amount=request.amount,
            reason=request.reason,
        )
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PaymentNotRefundableError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RefundAmountInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get payment details by ID. Client polls this until status != 'processing'."""
    try:
        return await get_payment_svc(db=db, payment_id=payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
