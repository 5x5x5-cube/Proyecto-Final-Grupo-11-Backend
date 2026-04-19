"""Payment service endpoints — our domain."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..schemas import InitiatePaymentRequest, PaymentConfirmationWebhook, PaymentResponse
from ..services.cart_client import CartExpiredError, CartNotFoundError
from ..services.payment_service import confirm_payment
from ..services.payment_service import get_payment as get_payment_svc
from ..services.payment_service import initiate_payment

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
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a payment. Tokenizes via gateway, saves payment method, fires adapter.

    Returns 202 immediately; client polls GET /{id} for result.
    """
    try:
        return await initiate_payment(db=db, user_id=user_id, request=request)
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
