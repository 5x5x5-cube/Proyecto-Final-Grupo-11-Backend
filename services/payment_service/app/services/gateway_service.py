"""Simulated gateway operations. In production, these would be SDK calls to the real gateway."""

import asyncio
import hashlib
import random
import secrets

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidTokenError
from ..models import PaymentMethodType, PaymentToken
from ..schemas import (
    GatewayProcessRequest,
    GatewayProcessResponse,
    TokenizeCardRequest,
    TokenizeRequest,
    TokenizeResponse,
    TokenizeTransferRequest,
    TokenizeWalletRequest,
)
from . import token_service

# ── Magic test cards (gateway's internal knowledge) ──

_MAGIC_DECLINE_CARDS = {
    hashlib.sha256(b"4000000000000002").hexdigest(): "insufficient_funds",
    hashlib.sha256(b"4000000000000069").hexdigest(): "expired_card",
}

_MIN_DELAY_SECONDS = 2
_MAX_DELAY_SECONDS = 6


# ── Tokenization ──


def _parse_tokenize_request(body: dict) -> TokenizeRequest:
    from pydantic import TypeAdapter

    adapter = TypeAdapter(TokenizeRequest)
    return adapter.validate_python(body)


async def tokenize(db: AsyncSession, body: dict) -> TokenizeResponse:
    """Tokenize any payment method. Simulates a gateway's tokenization API."""
    method = body.get("method", "credit_card")
    if method not in PaymentMethodType._value2member_map_:
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


# ── Payment processing ──


async def process_payment(
    db: AsyncSession,
    request: GatewayProcessRequest,
) -> GatewayProcessResponse:
    """Accept a payment for async processing. Returns pending immediately."""
    result = await db.execute(select(PaymentToken).where(PaymentToken.token == request.token))
    token = result.scalar_one_or_none()
    card_hash = token.method_data.get("numberHash") if token and token.method_data else None

    transaction_id = f"txn_{secrets.token_hex(12)}"

    # Schedule background processing (will call merchant webhook when done)
    asyncio.get_event_loop().create_task(
        _process_and_notify(
            payment_id=request.payment_id,
            card_number_hash=card_hash,
            webhook_url=request.webhook_url,
        )
    )

    return GatewayProcessResponse(
        transaction_id=transaction_id,
        status="pending",
    )


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
        pass  # webhook failure — payment stays in "processing"
