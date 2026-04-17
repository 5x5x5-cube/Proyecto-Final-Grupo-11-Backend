"""Simulated payment gateway endpoints.

These endpoints simulate what a real payment gateway (Stripe, PayU, etc.)
would provide. In production, these would be replaced by the gateway's SDK.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError
from ..schemas import GatewayProcessRequest, GatewayProcessResponse, TokenizeResponse
from ..services.gateway_service import process_payment, tokenize

router = APIRouter(prefix="/api/v1/gateway", tags=["gateway (simulated)"])


@router.post("/tokenize", response_model=TokenizeResponse, status_code=201)
async def tokenize_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Tokenize payment method data."""
    body: Dict[str, Any] = await request.json()
    try:
        return await tokenize(db=db, body=body)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())


@router.post("/process", response_model=GatewayProcessResponse, status_code=202)
async def process_payment_endpoint(
    request: GatewayProcessRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a payment for processing. Returns pending immediately."""
    return await process_payment(db=db, request=request)
