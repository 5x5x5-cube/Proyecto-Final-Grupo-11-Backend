"""Tests for payment_adapter: magic card handling."""

import hashlib

from app.services.payment_adapter import _resolve_payment


class TestResolvePayment:
    def test_approved_visa(self):
        card_hash = hashlib.sha256(b"4242424242424242").hexdigest()
        result = _resolve_payment(card_hash)
        assert result.approved is True
        assert result.transaction_id.startswith("txn_")
        assert result.error_code is None

    def test_declined_insufficient_funds(self):
        card_hash = hashlib.sha256(b"4000000000000002").hexdigest()
        result = _resolve_payment(card_hash)
        assert result.approved is False
        assert result.error_code == "insufficient_funds"

    def test_declined_expired_card(self):
        card_hash = hashlib.sha256(b"4000000000000069").hexdigest()
        result = _resolve_payment(card_hash)
        assert result.approved is False
        assert result.error_code == "expired_card"

    def test_unknown_card_approved(self):
        card_hash = hashlib.sha256(b"5105105105105100").hexdigest()
        result = _resolve_payment(card_hash)
        assert result.approved is True

    def test_none_hash_approved(self):
        """Non-card methods (wallet, transfer) pass None — always approved."""
        result = _resolve_payment(None)
        assert result.approved is True
