"""Simulated payment gateway endpoints.

These endpoints simulate what a real payment gateway (Stripe, PayU, etc.)
would provide. In production, these would be replaced by the gateway's SDK
and the PaymentToken table would live on their infrastructure.
"""

import asyncio
import hashlib
import random
import secrets
from typing import Any, Dict

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import InvalidTokenError
from ..models import PaymentToken
from ..schemas import GatewayProcessRequest, GatewayProcessResponse, TokenizeResponse
from ..services.gateway_service import tokenize

router = APIRouter(prefix="/api/v1/gateway", tags=["gateway (simulated)"])

# ── Magic test cards (gateway knows these internally) ──

_MAGIC_DECLINE_CARDS = {
    hashlib.sha256(b"4000000000000002").hexdigest(): "insufficient_funds",
    hashlib.sha256(b"4000000000000069").hexdigest(): "expired_card",
}

_MIN_DELAY_SECONDS = 2
_MAX_DELAY_SECONDS = 6


# ── Background processing ──


async def _process_and_notify(
    payment_id: str,
    card_number_hash: str | None,
    webhook_url: str,
) -> None:
    """Simulate gateway processing delay, then call the merchant webhook."""
    delay = random.uniform(_MIN_DELAY_SECONDS, _MAX_DELAY_SECONDS)  # nosec B311
    await asyncio.sleep(delay)

    transaction_id = f"txn_{secrets.token_hex(12)}"
    approved = True
    error_code = None

    if card_number_hash:
        decline_reason = _MAGIC_DECLINE_CARDS.get(card_number_hash)
        if decline_reason:
            approved = False
            error_code = decline_reason

    payload = {
        "paymentId": payment_id,
        "approved": approved,
        "transactionId": transaction_id,
        "errorCode": error_code,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:  # noqa: B110  # nosec B110
        pass  # webhook failure — payment stays in "processing" on the merchant side


# ── Endpoints ──


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
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a payment for processing. Returns pending immediately.

    The gateway processes asynchronously (2-6s) and calls the merchant's
    webhook with the result.
    """
    # Look up the token to get the card hash for magic card matching
    result = await db.execute(select(PaymentToken).where(PaymentToken.token == request.token))
    token = result.scalar_one_or_none()

    card_hash = token.method_data.get("numberHash") if token and token.method_data else None

    transaction_id = f"txn_{secrets.token_hex(12)}"

    # Schedule async processing
    background_tasks.add_task(
        _process_and_notify,
        payment_id=request.payment_id,
        card_number_hash=card_hash,
        webhook_url=request.webhook_url,
    )

    return GatewayProcessResponse(
        transaction_id=transaction_id,
        status="pending",
    )
