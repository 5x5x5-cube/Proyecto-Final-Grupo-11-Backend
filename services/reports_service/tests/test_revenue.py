import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import MonthlyRevenueReport, MonthlyRevenueSummary, TransactionDetail

client = TestClient(app)


def test_health_check():
    """Test que el servicio está funcionando."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test que el endpoint raíz retorna información del servicio."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "endpoints" in data
    assert "monthly_revenue" in data["endpoints"]


def test_monthly_revenue_requires_hotel_id():
    """Test que el endpoint requiere X-Hotel-Id header."""
    response = client.get("/api/v1/reports/revenue/monthly?month=1&year=2026")
    assert response.status_code == 401
    assert "X-Hotel-Id" in response.json()["detail"]


def test_available_periods_requires_hotel_id():
    """Test que el endpoint de periodos requiere X-Hotel-Id header."""
    response = client.get("/api/v1/reports/revenue/available-periods")
    assert response.status_code == 401
    assert "X-Hotel-Id" in response.json()["detail"]


def test_download_requires_hotel_id():
    """Test que el endpoint de descarga requiere X-Hotel-Id header."""
    response = client.get("/api/v1/reports/revenue/download?month=1&year=2026&format=pdf")
    assert response.status_code == 401


def test_monthly_revenue_validates_month():
    """Test que valida el rango del mes."""
    hotel_id = str(uuid.uuid4())
    response = client.get(
        "/api/v1/reports/revenue/monthly?month=13&year=2026",
        headers={"X-Hotel-Id": hotel_id},
    )
    assert response.status_code == 422  # Validation error


def test_monthly_revenue_validates_year():
    """Test que valida el rango del año."""
    hotel_id = str(uuid.uuid4())
    response = client.get(
        "/api/v1/reports/revenue/monthly?month=1&year=1900",
        headers={"X-Hotel-Id": hotel_id},
    )
    assert response.status_code == 422  # Validation error


# Tests de schemas


def test_transaction_detail_schema():
    """Test que el schema de TransactionDetail funciona correctamente."""
    tx = TransactionDetail(
        booking_code="BK-TEST123",
        booking_id=uuid.uuid4(),
        guest_name="Juan Pérez",
        check_in=date(2026, 1, 15),
        check_out=date(2026, 1, 20),
        nights=5,
        amount=Decimal("500000"),
        currency="COP",
        status="confirmed",
        created_at=datetime.now(),
    )
    assert tx.booking_code == "BK-TEST123"
    assert tx.nights == 5


def test_monthly_revenue_summary_schema():
    """Test que el schema de MonthlyRevenueSummary funciona correctamente."""
    summary = MonthlyRevenueSummary(
        hotel_id=uuid.uuid4(),
        month=1,
        year=2026,
        gross_revenue=Decimal("1000000"),
        cancellations_amount=Decimal("100000"),
        refunds_amount=Decimal("50000"),
        net_revenue=Decimal("850000"),
        total_bookings=10,
        confirmed_bookings=8,
        cancelled_bookings=2,
        pending_bookings=0,
    )
    assert summary.net_revenue == Decimal("850000")
    assert summary.total_bookings == 10
