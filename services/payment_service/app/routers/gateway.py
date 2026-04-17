"""Simulated payment gateway endpoints.

These endpoints simulate what a real payment gateway (Stripe, PayU, etc.)
would provide. In production, these would be replaced by the gateway's SDK
and the PaymentToken table would live on their infrastructure.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError
from ..schemas import TokenizeResponse
from ..services.gateway_service import tokenize

router = APIRouter(prefix="/api/v1/gateway", tags=["gateway (simulated)"])


@router.post("/tokenize", response_model=TokenizeResponse, status_code=201)
async def tokenize_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Tokenize payment method data. Simulates a real gateway's tokenization API."""
    body: Dict[str, Any] = await request.json()
    try:
        return await tokenize(db=db, body=body)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors())
