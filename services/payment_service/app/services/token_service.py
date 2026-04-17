import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from ..exceptions import InvalidTokenError
from ..models import PaymentToken


def validate_luhn(card_number: str) -> bool:
    """Validate a card number using the Luhn algorithm."""
    digits = card_number.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) < 13 or len(digits) > 19:
        return False

    total = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        n = int(digit)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def detect_brand(card_number: str) -> str:
    """Detect the card brand from the card number."""
    digits = card_number.replace(" ", "").replace("-", "")
    if digits.startswith("4"):
        return "visa"
    if digits[:2] in ("34", "37"):
        return "amex"
    prefix2 = int(digits[:2]) if len(digits) >= 2 else 0
    if 51 <= prefix2 <= 55:
        return "mastercard"
    return "unknown"


def hash_card_number(card_number: str) -> str:
    """Create a SHA-256 hash of the card number for magic-card matching."""
    digits = card_number.replace(" ", "").replace("-", "")
    return hashlib.sha256(digits.encode()).hexdigest()


async def create_token(
    db: AsyncSession,
    card_number: str,
    card_holder: str,
    expiry: str,
    cvv: str,
) -> PaymentToken:
    """Validate card details and create a payment token. CVV is validated but never stored."""
    digits = card_number.replace(" ", "").replace("-", "")

    if not validate_luhn(digits):
        raise InvalidTokenError("Invalid card number")

    if not re.match(r"^\d{3,4}$", cvv):
        raise InvalidTokenError("Invalid CVV")

    if not re.match(r"^\d{2}/\d{2}$", expiry):
        raise InvalidTokenError("Invalid expiry format")

    month_str, year_str = expiry.split("/")
    month = int(month_str)
    year = 2000 + int(year_str)

    if month < 1 or month > 12:
        raise InvalidTokenError("Invalid expiry month")

    now = datetime.now(timezone.utc)
    if year < now.year or (year == now.year and month < now.month):
        raise InvalidTokenError("Card has expired")

    brand = detect_brand(digits)
    last4 = digits[-4:]
    card_hash = hash_card_number(digits)

    token = PaymentToken(
        id=uuid.uuid4(),
        token=f"tok_{secrets.token_hex(16)}",
        card_last4=last4,
        card_brand=brand,
        card_holder=card_holder.strip(),
        card_number_hash=card_hash,
        expiry_month=month,
        expiry_year=year,
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token
