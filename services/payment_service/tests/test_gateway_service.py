"""Tests for the simulated gateway service (tokenization)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app


def _override_db(db_mock):
    async def override():
        yield db_mock

    return override


class TestGatewayTokenize:
    async def test_tokenize_card_success(self):
        db = AsyncMock()

        async def fake_refresh(obj):
            if obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
            if obj.expires_at is None:
                obj.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/gateway/tokenize",
                    json={
                        "method": "credit_card",
                        "cardNumber": "4242424242424242",
                        "cardHolder": "Carlos Martinez",
                        "expiry": "12/28",
                        "cvv": "123",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["token"].startswith("tok_")
            assert data["method"] == "credit_card"
            assert data["displayLabel"] == "Visa •••• 4242"
            assert data["cardLast4"] == "4242"
            assert data["cardBrand"] == "visa"
        finally:
            app.dependency_overrides.clear()

    async def test_tokenize_wallet_success(self):
        db = AsyncMock()

        async def fake_refresh(obj):
            if obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
            if obj.expires_at is None:
                obj.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/gateway/tokenize",
                    json={
                        "method": "digital_wallet",
                        "walletProvider": "paypal",
                        "walletEmail": "carlos@email.com",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["token"].startswith("tok_")
            assert data["method"] == "digital_wallet"
            assert "paypal" in data["displayLabel"].lower()
            assert data["walletProvider"] == "paypal"
            assert data["cardLast4"] is None
        finally:
            app.dependency_overrides.clear()

    async def test_tokenize_transfer_success(self):
        db = AsyncMock()

        async def fake_refresh(obj):
            if obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)
            if obj.expires_at is None:
                obj.expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

        db.refresh = AsyncMock(side_effect=fake_refresh)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/gateway/tokenize",
                    json={
                        "method": "transfer",
                        "bankCode": "001",
                        "accountNumber": "12345678901234",
                        "accountHolder": "Carlos Martinez",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["token"].startswith("tok_")
            assert data["method"] == "transfer"
            assert data["bankCode"] == "001"
        finally:
            app.dependency_overrides.clear()

    async def test_tokenize_invalid_luhn(self):
        db = AsyncMock()

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/gateway/tokenize",
                    json={
                        "method": "credit_card",
                        "cardNumber": "1234567890123456",
                        "cardHolder": "Test",
                        "expiry": "12/28",
                        "cvv": "123",
                    },
                )

            assert response.status_code == 400
            assert "Invalid card number" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    async def test_tokenize_missing_cvv(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/gateway/tokenize",
                json={
                    "method": "credit_card",
                    "cardNumber": "4242424242424242",
                    "cardHolder": "Test",
                    "expiry": "12/28",
                },
            )

        assert response.status_code == 422

    async def test_tokenize_invalid_method(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/gateway/tokenize",
                json={"method": "bitcoin", "address": "abc123"},
            )

        assert response.status_code == 400

    async def test_tokenize_expired_card(self):
        db = AsyncMock()
        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/gateway/tokenize",
                    json={
                        "method": "credit_card",
                        "cardNumber": "4242424242424242",
                        "cardHolder": "Test",
                        "expiry": "01/20",
                        "cvv": "123",
                    },
                )

            assert response.status_code == 400
            assert "expired" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
