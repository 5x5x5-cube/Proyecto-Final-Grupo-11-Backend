"""Tests for payment_adapter: magic card handling."""

import hashlib

from app.services.payment_adapter import process_payment


class TestProcessPayment:
    async def test_approved_visa(self):
        card_hash = hashlib.sha256(b"4242424242424242").hexdigest()
        result = await process_payment(card_number_hash=card_hash, amount=100000.0)
        assert result.approved is True
        assert result.transaction_id.startswith("txn_")
        assert result.error_code is None

    async def test_declined_insufficient_funds(self):
        card_hash = hashlib.sha256(b"4000000000000002").hexdigest()
        result = await process_payment(card_number_hash=card_hash, amount=100000.0)
        assert result.approved is False
        assert result.error_code == "insufficient_funds"
        assert result.transaction_id.startswith("txn_")

    async def test_declined_expired_card(self):
        card_hash = hashlib.sha256(b"4000000000000069").hexdigest()
        result = await process_payment(card_number_hash=card_hash, amount=100000.0)
        assert result.approved is False
        assert result.error_code == "expired_card"

    async def test_unknown_card_approved(self):
        card_hash = hashlib.sha256(b"5105105105105100").hexdigest()
        result = await process_payment(card_number_hash=card_hash, amount=50000.0)
        assert result.approved is True
        assert result.error_code is None
