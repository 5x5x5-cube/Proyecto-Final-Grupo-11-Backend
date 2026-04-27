"""Tests for token_service: Luhn validation, brand detection, token creation."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.exceptions import InvalidTokenError
from app.services.token_service import (
    create_card_token,
    detect_brand,
    hash_card_number,
    validate_luhn,
)

# ---------------------------------------------------------------------------
# Luhn validation
# ---------------------------------------------------------------------------


class TestValidateLuhn:
    def test_valid_visa(self):
        assert validate_luhn("4242424242424242") is True

    def test_valid_mastercard(self):
        assert validate_luhn("5105105105105100") is True

    def test_valid_amex(self):
        assert validate_luhn("378282246310005") is True

    def test_invalid_number(self):
        assert validate_luhn("1234567890123456") is False

    def test_too_short(self):
        assert validate_luhn("123") is False

    def test_non_numeric(self):
        assert validate_luhn("abcdefghijklmnop") is False

    def test_empty_string(self):
        assert validate_luhn("") is False

    def test_with_spaces(self):
        assert validate_luhn("4242 4242 4242 4242") is True

    def test_decline_card(self):
        assert validate_luhn("4000000000000002") is True

    def test_expired_card_magic(self):
        assert validate_luhn("4000000000000069") is True


# ---------------------------------------------------------------------------
# Brand detection
# ---------------------------------------------------------------------------


class TestDetectBrand:
    def test_visa(self):
        assert detect_brand("4242424242424242") == "visa"

    def test_mastercard_51(self):
        assert detect_brand("5105105105105100") == "mastercard"

    def test_mastercard_55(self):
        assert detect_brand("5500000000000004") == "mastercard"

    def test_amex_34(self):
        assert detect_brand("340000000000009") == "amex"

    def test_amex_37(self):
        assert detect_brand("378282246310005") == "amex"

    def test_unknown(self):
        assert detect_brand("6011000000000004") == "unknown"


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


class TestCreateToken:
    async def test_create_token_valid_card(self):
        db = AsyncMock()
        token = await create_card_token(
            method="credit_card",
            db=db,
            card_number="4242424242424242",
            card_holder="John Doe",
            expiry="12/30",
            cvv="123",
        )
        assert token.method_data["last4"] == "4242"
        assert token.method_data["brand"] == "visa"
        assert token.method_data["holder"] == "John Doe"
        assert token.token.startswith("tok_")
        assert token.expires_at > datetime.now(timezone.utc)
        db.add.assert_called_once()
        db.commit.assert_called_once()

    async def test_create_token_invalid_luhn(self):
        db = AsyncMock()
        with pytest.raises(InvalidTokenError, match="Invalid card number"):
            await create_card_token(
                method="credit_card",
                db=db,
                card_number="1234567890123456",
                card_holder="John Doe",
                expiry="12/30",
                cvv="123",
            )

    async def test_create_token_invalid_cvv(self):
        db = AsyncMock()
        with pytest.raises(InvalidTokenError, match="Invalid CVV"):
            await create_card_token(
                method="credit_card",
                db=db,
                card_number="4242424242424242",
                card_holder="John Doe",
                expiry="12/30",
                cvv="12",
            )

    async def test_create_token_expired_card(self):
        db = AsyncMock()
        with pytest.raises(InvalidTokenError, match="Card has expired"):
            await create_card_token(
                method="credit_card",
                db=db,
                card_number="4242424242424242",
                card_holder="John Doe",
                expiry="01/20",
                cvv="123",
            )

    async def test_create_token_invalid_month(self):
        db = AsyncMock()
        with pytest.raises(InvalidTokenError, match="Invalid expiry month"):
            await create_card_token(
                method="credit_card",
                db=db,
                card_number="4242424242424242",
                card_holder="John Doe",
                expiry="13/30",
                cvv="123",
            )

    async def test_no_cvv_stored_in_token(self):
        """Verify CVV is never stored in the token model."""
        db = AsyncMock()
        token = await create_card_token(
            method="credit_card",
            db=db,
            card_number="4242424242424242",
            card_holder="John Doe",
            expiry="12/30",
            cvv="123",
        )
        # Ensure CVV is never in method_data
        assert "cvv" not in token.method_data

    async def test_card_number_hash_stored(self):
        """Verify the card number hash is stored for gateway matching."""
        db = AsyncMock()
        token = await create_card_token(
            method="credit_card",
            db=db,
            card_number="4242424242424242",
            card_holder="John Doe",
            expiry="12/30",
            cvv="123",
        )
        expected_hash = hash_card_number("4242424242424242")
        assert token.method_data["numberHash"] == expected_hash
