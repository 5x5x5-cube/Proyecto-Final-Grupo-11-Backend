import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from ..schemas import InitiatePaymentRequest, PaymentResponse, TokenizeResponse
from ..services.cart_client import CartExpiredError, CartNotFoundError
from ..services.payment_service import get_payment as get_payment_svc
from ..services.payment_service import initiate_payment, tokenize_method

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


def get_user_id(request: Request) -> uuid.UUID:
    """Extract and validate the X-User-Id header; return 401 if missing or invalid."""
    raw = request.headers.get("X-User-Id")
    if not raw:
        raise HTTPException(status_code=401, detail="X-User-Id header is required")
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-User-Id header is not a valid UUID")


@router.post("/tokenize", response_model=TokenizeResponse, status_code=201)
async def tokenize_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Tokenize payment method data. Accepts card, wallet, or transfer based on 'method' field."""
    body: Dict[str, Any] = await request.json()
    try:
        return await tokenize_method(db=db, body=body)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())


@router.post("/initiate", response_model=PaymentResponse, status_code=202)
async def initiate_payment_endpoint(
    request: InitiatePaymentRequest,
    user_id: uuid.UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a payment for a booking."""
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


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_endpoint(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get payment details by ID."""
    try:
        return await get_payment_svc(db=db, payment_id=payment_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
