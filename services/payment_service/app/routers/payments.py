"""Payment service endpoints — our domain."""

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..models import ExchangeRate
from ..schemas import (
    ExchangeRateResponse,
    InitiatePaymentRequest,
    PaymentAdminListResponse,
    PaymentConfirmationWebhook,
    PaymentResponse,
)
from ..services.cart_client import CartExpiredError, CartNotFoundError
from ..services.payment_service import confirm_payment
from ..services.payment_service import get_payment as get_payment_svc
from ..services.payment_service import initiate_payment
from ..services.payment_service import list_payments as list_payments_svc

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
