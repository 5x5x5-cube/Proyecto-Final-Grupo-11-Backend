import hashlib
import secrets
from dataclasses import dataclass


@dataclass
class PaymentResult:
    approved: bool
    transaction_id: str
    error_code: str | None


# Pre-computed hashes for magic test cards
_MAGIC_DECLINE_CARDS = {
    # 4000000000000002 → insufficient_funds
    hashlib.sha256(b"4000000000000002").hexdigest(): "insufficient_funds",
    # 4000000000000069 → expired_card
    hashlib.sha256(b"4000000000000069").hexdigest(): "expired_card",
}


async def process_payment(
    card_number_hash: str,
    amount: float,
) -> PaymentResult:
    """Simulate an external payment gateway call.

    Uses the card_number_hash to match magic test cards without ever seeing
    the real card number.
    """
    transaction_id = f"txn_{secrets.token_hex(12)}"

    error_code = _MAGIC_DECLINE_CARDS.get(card_number_hash)
    if error_code:
        return PaymentResult(approved=False, transaction_id=transaction_id, error_code=error_code)

    return PaymentResult(approved=True, transaction_id=transaction_id, error_code=None)
