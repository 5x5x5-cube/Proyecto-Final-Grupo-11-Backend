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


async def create_card_token(
    db: AsyncSession,
    method: str,
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
    brand_label = brand.capitalize() if brand != "unknown" else "Card"

    token = PaymentToken(
        id=uuid.uuid4(),
        token=f"tok_{secrets.token_hex(16)}",
        method=method,
        display_label=f"{brand_label} •••• {last4}",
        method_data={
            "last4": last4,
            "brand": brand,
            "holder": card_holder.strip(),
            "numberHash": card_hash,
            "expiryMonth": month,
            "expiryYear": year,
        },
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def create_wallet_token(
    db: AsyncSession,
    wallet_provider: str,
    wallet_email: str,
) -> PaymentToken:
    """Create a token for a digital wallet payment."""
    if not wallet_provider or not wallet_email:
        raise InvalidTokenError("Wallet provider and email are required")

    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", wallet_email):
        raise InvalidTokenError("Invalid wallet email")

    provider_label = wallet_provider.capitalize()

    token = PaymentToken(
        id=uuid.uuid4(),
        token=f"tok_{secrets.token_hex(16)}",
        method="digital_wallet",
        display_label=f"{provider_label} ({wallet_email})",
        method_data={
            "provider": wallet_provider.lower(),
            "email": wallet_email,
        },
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def create_transfer_token(
    db: AsyncSession,
    bank_code: str,
    account_number: str,
    account_holder: str,
) -> PaymentToken:
    """Create a token for a bank transfer payment."""
    if not bank_code or not account_number or not account_holder:
        raise InvalidTokenError("Bank code, account number, and holder are required")

    digits = account_number.replace(" ", "").replace("-", "")
    if not digits.isdigit() or len(digits) < 6:
        raise InvalidTokenError("Invalid account number")

    last4 = digits[-4:]

    token = PaymentToken(
        id=uuid.uuid4(),
        token=f"tok_{secrets.token_hex(16)}",
        method="transfer",
        display_label=f"Bank {bank_code} •••• {last4}",
        method_data={
            "bankCode": bank_code,
            "accountLast4": last4,
            "holder": account_holder.strip(),
        },
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token
