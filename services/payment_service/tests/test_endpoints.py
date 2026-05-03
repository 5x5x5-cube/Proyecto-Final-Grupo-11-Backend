"""Tests for payment endpoints using mocked DB."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.main import app
from app.models import Payment, PaymentToken, UserPaymentMethod
from app.schemas import CartData
from app.services.token_service import hash_card_number

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

USER_ID = uuid.UUID("c1000000-0000-0000-0000-000000000001")
CART_ID = uuid.UUID("d1000000-0000-0000-0000-000000000001")

MOCK_CART = CartData.model_validate(
    {
        "id": str(CART_ID),
        "userId": str(USER_ID),
        "roomId": "b1000000-0000-0000-0000-000000000001",
        "hotelId": "a1000000-0000-0000-0000-000000000001",
        "holdId": "h1000000-0000-0000-0000-000000000001",
        "checkIn": "2026-05-01",
        "checkOut": "2026-05-04",
        "guests": 2,
        "hotelName": "Hotel Caribe Plaza",
        "roomName": "Standard",
        "priceBreakdown": {
            "pricePerNight": "250000.00",
            "nights": 3,
            "subtotal": "750000.00",
            "vat": "142500.00",
            "serviceFee": "0",
            "total": "892500.00",
            "currency": "COP",
        },
    }
)


def _make_token(
    card_number: str = "4242424242424242",
    expired: bool = False,
) -> PaymentToken:
    now = datetime.now(timezone.utc)
    return PaymentToken(
        id=uuid.uuid4(),
        token="tok_test1234567890abcdef1234567890ab",
        method="credit_card",
        display_label=f"Visa •••• {card_number[-4:]}",
        method_data={
            "last4": card_number[-4:],
            "brand": "visa",
            "holder": "John Doe",
            "numberHash": hash_card_number(card_number),
            "expiryMonth": 12,
            "expiryYear": 2030,
        },
        created_at=now - timedelta(minutes=10 if not expired else 20),
        expires_at=now + timedelta(minutes=5) if not expired else now - timedelta(minutes=5),
    )


def _make_payment_method(token: PaymentToken) -> UserPaymentMethod:
    return UserPaymentMethod(
        id=uuid.uuid4(),
        user_id=USER_ID,
        gateway_token=token.token,
        method_type="credit_card",
        display_label=token.display_label,
        card_last4=token.method_data.get("last4"),
        card_brand=token.method_data.get("brand"),
        created_at=datetime.now(timezone.utc),
    )


def _make_payment(pm: UserPaymentMethod, status: str = "approved") -> Payment:
    return Payment(
        id=uuid.uuid4(),
        user_id=USER_ID,
        payment_method_id=pm.id,
        amount=500000.00,
        currency="COP",
        status=status,
        transaction_id="txn_abc123",
        error_code=None,
        created_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
    )


def _override_db(db_mock):
    """Create a dependency override that returns the mock session."""

    async def _get_db_override():
        yield db_mock

    return _get_db_override


# ---------------------------------------------------------------------------
# Tokenize endpoint
# ---------------------------------------------------------------------------


class TestTokenizeEndpoint:
    async def test_tokenize_valid_card(self):
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
                        "cardHolder": "John Doe",
                        "expiry": "12/30",
                        "cvv": "123",
                    },
                )

            assert response.status_code == 201
            data = response.json()
            assert data["token"].startswith("tok_")
            assert data["cardLast4"] == "4242"
            assert data["cardBrand"] == "visa"
            assert "expiresAt" in data
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
                        "cardHolder": "John Doe",
                        "expiry": "12/30",
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
                    "cardHolder": "John Doe",
                    "expiry": "12/30",
                },
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Initiate endpoint
# ---------------------------------------------------------------------------


class TestInitiateEndpoint:
    @patch("app.services.payment_service.payment_adapter")
    @patch("app.services.payment_service.cart_client")
    async def test_initiate_returns_processing(self, mock_cart, mock_adapter):
        """Initiate returns 202 with status=processing immediately."""
        token = _make_token("4242424242424242")

        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = token
        db.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if hasattr(obj, "status") and obj.id is None:
                obj.id = uuid.uuid4()
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)

        db.refresh = AsyncMock(side_effect=fake_refresh)
        mock_cart.get_cart = AsyncMock(return_value=MOCK_CART)
        # Adapter fires in background — mock it to not actually sleep/call webhook
        mock_adapter.submit_to_gateway = AsyncMock(
            return_value=MagicMock(transaction_id="txn_mock", status="pending")
        )

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/payments/initiate",
                    json={
                        "token": token.token,
                        "cartId": str(CART_ID),
                        "method": "credit_card",
                    },
                    headers={"X-User-Id": str(USER_ID)},
                )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "processing"
            assert data["paymentId"] is not None
            assert data["paymentMethod"]["cardLast4"] == "4242"
            assert data["paymentMethod"]["displayLabel"] == "Visa •••• 4242"
            assert data["message"] is None  # no message while processing
        finally:
            app.dependency_overrides.clear()

    @patch("app.services.payment_service.payment_adapter")
    @patch("app.services.payment_service.cart_client")
    async def test_initiate_decline_card_still_returns_processing(self, mock_cart, mock_adapter):
        """Even a decline card returns processing initially — result comes via polling."""
        token = _make_token("4000000000000002")

        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = token
        db.execute = AsyncMock(return_value=mock_result)

        async def fake_refresh(obj):
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)

        db.refresh = AsyncMock(side_effect=fake_refresh)
        mock_cart.get_cart = AsyncMock(return_value=MOCK_CART)
        mock_adapter.submit_to_gateway = AsyncMock(
            return_value=MagicMock(transaction_id="txn_mock", status="pending")
        )

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/payments/initiate",
                    json={
                        "token": token.token,
                        "cartId": str(CART_ID),
                    },
                    headers={"X-User-Id": str(USER_ID)},
                )

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "processing"
        finally:
            app.dependency_overrides.clear()

    async def test_initiate_expired_token(self):
        token = _make_token(expired=True)

        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = token
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/payments/initiate",
                    json={
                        "token": token.token,
                        "cartId": str(CART_ID),
                    },
                    headers={"X-User-Id": str(USER_ID)},
                )

            assert response.status_code == 400
            assert "expired" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    async def test_initiate_invalid_token(self):
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/payments/initiate",
                    json={
                        "token": "tok_invalid",
                        "cartId": str(CART_ID),
                    },
                    headers={"X-User-Id": str(USER_ID)},
                )

            assert response.status_code == 400
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    async def test_initiate_missing_user_id(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/payments/initiate",
                json={
                    "token": "tok_test",
                    "cartId": str(CART_ID),
                },
            )

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Get payment endpoint
# ---------------------------------------------------------------------------


class TestGetPaymentEndpoint:
    async def test_get_payment_found(self):
        token = _make_token()
        pm = _make_payment_method(token)
        payment = _make_payment(pm)

        db = AsyncMock()

        # First call returns Payment, second returns UserPaymentMethod
        payment_result = MagicMock()
        payment_result.scalar_one_or_none.return_value = payment
        pm_result = MagicMock()
        pm_result.scalar_one_or_none.return_value = pm
        db.execute = AsyncMock(side_effect=[payment_result, pm_result])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/payments/{payment.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["paymentId"] == str(payment.id)
            assert data["status"] == "approved"
        finally:
            app.dependency_overrides.clear()

    async def test_get_payment_not_found(self):
        db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(f"/api/v1/payments/{uuid.uuid4()}")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Confirmation webhook
# ---------------------------------------------------------------------------


class TestConfirmationWebhook:
    @patch("app.services.payment_service.notify_payment_confirmed", new_callable=AsyncMock)
    async def test_webhook_approves_payment(self, mock_notify):
        """Webhook updates payment from processing to approved."""
        token = _make_token()
        pm = _make_payment_method(token)
        payment = _make_payment(pm, status="processing")

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = payment
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/payments/{payment.id}/confirmation",
                    json={
                        "paymentId": str(payment.id),
                        "approved": True,
                        "transactionId": "txn_test123",
                        "errorCode": None,
                    },
                )

            assert response.status_code == 200
            assert payment.status == "approved"
            assert payment.transaction_id == "txn_test123"
        finally:
            app.dependency_overrides.clear()

    @patch("app.services.payment_service.notify_payment_declined", new_callable=AsyncMock)
    async def test_webhook_declines_payment(self, mock_notify):
        """Webhook updates payment from processing to declined."""
        token = _make_token()
        pm = _make_payment_method(token)
        payment = _make_payment(pm, status="processing")

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = payment
        db.execute = AsyncMock(return_value=mock_result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/payments/{payment.id}/confirmation",
                    json={
                        "paymentId": str(payment.id),
                        "approved": False,
                        "transactionId": "txn_test456",
                        "errorCode": "insufficient_funds",
                    },
                )

            assert response.status_code == 200
            assert payment.status == "declined"
            assert payment.error_code == "insufficient_funds"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin: list payments (HU4.4)
# ---------------------------------------------------------------------------


class TestAdminListPayments:
    """GET /api/v1/payments — admin listing with filters and pagination."""

    def _setup_db(self, *, total: int, items: list):
        """Build an AsyncMock that returns count then list on consecutive execute calls."""
        db = AsyncMock()
        count_result = MagicMock()
        count_result.scalar.return_value = total
        list_result = MagicMock()
        list_result.all.return_value = items
        db.execute = AsyncMock(side_effect=[count_result, list_result])
        return db

    async def test_list_returns_paginated_response(self):
        token = _make_token()
        pm = _make_payment_method(token)
        p1 = _make_payment(pm, status="approved")
        p2 = _make_payment(pm, status="declined")
        db = self._setup_db(total=2, items=[(p1, pm), (p2, pm)])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert data["page"] == 1
            assert data["pageSize"] == 20
            assert data["totalPages"] == 1
            assert len(data["items"]) == 2
            first = data["items"][0]
            assert first["id"] == str(p1.id)
            assert first["status"] == "approved"
            assert first["methodLabel"] == pm.display_label
            assert first["method"] == "credit_card"
        finally:
            app.dependency_overrides.clear()

    async def test_list_empty_returns_zero_total_pages(self):
        db = self._setup_db(total=0, items=[])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["totalPages"] == 0
            assert data["items"] == []
        finally:
            app.dependency_overrides.clear()

    async def test_list_status_filter_passes_through(self):
        token = _make_token()
        pm = _make_payment_method(token)
        approved = _make_payment(pm, status="approved")
        db = self._setup_db(total=1, items=[(approved, pm)])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments?status=approved")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert all(item["status"] == "approved" for item in data["items"])
        finally:
            app.dependency_overrides.clear()

    async def test_list_pagination_default_pagesize_20(self):
        db = self._setup_db(total=50, items=[])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments")

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["pageSize"] == 20
            assert data["total"] == 50
            # 50 items / 20 per page = 3 pages (ceil)
            assert data["totalPages"] == 3
        finally:
            app.dependency_overrides.clear()

    async def test_list_custom_page_and_pagesize(self):
        db = self._setup_db(total=50, items=[])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments?page=2&pageSize=10")

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["pageSize"] == 10
            assert data["totalPages"] == 5  # 50 / 10
        finally:
            app.dependency_overrides.clear()

    async def test_list_validates_page_bounds(self):
        # page < 1 → 422
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/payments?page=0")
        assert response.status_code == 422

        # pageSize > 100 → 422 (prevents resource exhaustion via huge page sizes)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/payments?pageSize=200")
        assert response.status_code == 422

    async def test_list_accepts_combined_filters(self):
        db = self._setup_db(total=1, items=[])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/payments"
                    "?status=approved&method=credit_card"
                    "&dateFrom=2026-01-01T00:00:00&dateTo=2026-12-31T23:59:59"
                    "&amountMin=100&amountMax=5000000"
                )

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin: payments summary (HU4.4)
# ---------------------------------------------------------------------------


class TestAdminPaymentsSummary:
    """GET /api/v1/payments/summary — aggregated metrics."""

    def _row(self, status: str, count: int, amount: float):
        """Build a row mock matching what GROUP BY status returns."""
        row = MagicMock()
        row.status = status
        row.count = count
        row.amount = amount
        return row

    def _setup_db(self, rows: list):
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_summary_with_mixed_statuses(self):
        rows = [
            self._row("approved", 8, 4_000_000.0),
            self._row("declined", 2, 500_000.0),
            self._row("refunded", 1, 250_000.0),
            self._row("processing", 3, 0.0),
        ]
        db = self._setup_db(rows)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["totalProcessed"] == 4_000_000.0
            assert data["totalDeclined"] == 500_000.0
            assert data["totalRefunded"] == 250_000.0
            assert data["approvedCount"] == 8
            assert data["declinedCount"] == 2
            assert data["refundedCount"] == 1
            assert data["processingCount"] == 3
            assert data["transactionCount"] == 14
            # 8 / (8 + 2) = 0.8
            assert data["approvalRate"] == 0.8
            assert data["currency"] == "COP"
        finally:
            app.dependency_overrides.clear()

    async def test_summary_no_payments_returns_zeros(self):
        db = self._setup_db([])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["totalProcessed"] == 0
            assert data["transactionCount"] == 0
            # No decided payments → approval rate is 0, not NaN
            assert data["approvalRate"] == 0.0
        finally:
            app.dependency_overrides.clear()

    async def test_summary_only_processing_does_not_divide_by_zero(self):
        # Only `processing` rows means decided count = 0.
        rows = [self._row("processing", 5, 0.0)]
        db = self._setup_db(rows)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/summary")

            assert response.status_code == 200
            data = response.json()
            assert data["approvalRate"] == 0.0
            assert data["processingCount"] == 5
        finally:
            app.dependency_overrides.clear()

    async def test_summary_accepts_date_range(self):
        db = self._setup_db([self._row("approved", 1, 100.0)])

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/payments/summary"
                    "?dateFrom=2026-01-01T00:00:00&dateTo=2026-12-31T23:59:59"
                )

            assert response.status_code == 200
            assert response.json()["totalProcessed"] == 100.0
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Admin: payments CSV export (HU4.4)
# ---------------------------------------------------------------------------


class TestAdminExportPayments:
    """GET /api/v1/payments/export — CSV download."""

    async def test_export_returns_csv_with_header_and_rows(self):
        token = _make_token()
        pm = _make_payment_method(token)
        p1 = _make_payment(pm, status="approved")
        p2 = _make_payment(pm, status="declined")

        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = [(p1, pm), (p2, pm)]
        db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/export")

            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/csv")
            assert "attachment" in response.headers["content-disposition"]
            assert "transactions.csv" in response.headers["content-disposition"]

            body = response.text
            lines = body.strip().splitlines()
            assert lines[0].startswith("id,user_id,amount,currency,method,method_label,status")
            # 2 data rows + header
            assert len(lines) == 3
            assert str(p1.id) in lines[1]
            assert "approved" in lines[1]
            assert "declined" in lines[2]
        finally:
            app.dependency_overrides.clear()

    async def test_export_unsupported_format_returns_400(self):
        db = AsyncMock()

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/export?format=xlsx")

            assert response.status_code == 400
            assert "CSV" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    async def test_export_empty_returns_only_header(self):
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/payments/export")

            assert response.status_code == 200
            lines = response.text.strip().splitlines()
            assert len(lines) == 1  # only header
        finally:
            app.dependency_overrides.clear()

    async def test_export_accepts_filters(self):
        db = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        app.dependency_overrides[get_db] = _override_db(db)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/payments/export"
                    "?status=approved&method=credit_card"
                    "&dateFrom=2026-01-01T00:00:00&amountMin=100"
                )

            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Model security
# ---------------------------------------------------------------------------


class TestModelSecurity:
    def test_payment_token_has_no_cvv_field(self):
        """Verify the PaymentToken model has no CVV field."""
        columns = [c.name for c in PaymentToken.__table__.columns]
        assert "cvv" not in columns

    def test_payment_has_no_cvv_field(self):
        """Verify the Payment model has no CVV field."""
        columns = [c.name for c in Payment.__table__.columns]
        assert "cvv" not in columns
