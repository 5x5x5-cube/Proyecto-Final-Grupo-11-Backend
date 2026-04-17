"""Simulated external payment gateway (Payment Adapter).

Processes payments asynchronously with a realistic delay (2-6s),
then calls back the PaymentConfirmation webhook on the payment service.
"""

import asyncio
import hashlib
import random
import secrets
import uuid
from dataclasses import dataclass

import httpx


@dataclass
class PaymentResult:
    approved: bool
    transaction_id: str
    error_code: str | None


# Pre-computed hashes for magic test cards
_MAGIC_DECLINE_CARDS = {
    hashlib.sha256(b"4000000000000002").hexdigest(): "insufficient_funds",
    hashlib.sha256(b"4000000000000069").hexdigest(): "expired_card",
}

# Simulate realistic gateway latency
_MIN_DELAY_SECONDS = 2
_MAX_DELAY_SECONDS = 6


def _resolve_payment(card_number_hash: str | None) -> PaymentResult:
    """Determine payment outcome based on magic card hashes."""
    transaction_id = f"txn_{secrets.token_hex(12)}"

    if card_number_hash:
        error_code = _MAGIC_DECLINE_CARDS.get(card_number_hash)
        if error_code:
            return PaymentResult(
                approved=False, transaction_id=transaction_id, error_code=error_code
            )

    return PaymentResult(approved=True, transaction_id=transaction_id, error_code=None)


async def process_payment_async(
    payment_id: uuid.UUID,
    card_number_hash: str | None,
    webhook_url: str,
) -> None:
    """Simulate gateway processing: delay, then call back the webhook.

    This runs as a fire-and-forget background task, mimicking how a real
    payment gateway (Stripe, PayU, etc.) would process asynchronously and
    notify via webhook.
    """
    delay = random.uniform(_MIN_DELAY_SECONDS, _MAX_DELAY_SECONDS)  # nosec B311
    await asyncio.sleep(delay)

    result = _resolve_payment(card_number_hash)

    # Call the PaymentConfirmation webhook
    payload = {
        "paymentId": str(payment_id),
        "approved": result.approved,
        "transactionId": result.transaction_id,
        "errorCode": result.error_code,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(webhook_url, json=payload)
    except Exception:  # noqa: B110  # nosec B110
        pass  # gateway callback failure — payment stays in "processing"
