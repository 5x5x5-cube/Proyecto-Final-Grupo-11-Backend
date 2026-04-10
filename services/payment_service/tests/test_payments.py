from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_initiate_payment():
    """Test payment initiation"""
    response = client.post(
        "/api/v1/payments/initiate",
        json={
            "booking_id": "test-booking-123",
            "amount": 100.50,
            "currency": "USD",
            "payment_method": "credit_card",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "payment_id" in data
    assert data["booking_id"] == "test-booking-123"
    assert data["amount"] == 100.50
    assert data["status"] == "pending"
    assert data["payment_method"] == "credit_card"


def test_get_payment():
    """Test get payment by ID"""
    # First create a payment
    create_response = client.post(
        "/api/v1/payments/initiate",
        json={
            "booking_id": "test-booking-456",
            "amount": 200.00,
            "currency": "USD",
            "payment_method": "paypal",
        },
    )
    payment_id = create_response.json()["payment_id"]

    # Then get it
    response = client.get(f"/api/v1/payments/{payment_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["payment_id"] == payment_id
    assert data["booking_id"] == "test-booking-456"


def test_get_payment_not_found():
    """Test get non-existent payment"""
    response = client.get("/api/v1/payments/non-existent-id")
    assert response.status_code == 404


def test_confirm_payment():
    """Test payment confirmation"""
    # Create a payment
    create_response = client.post(
        "/api/v1/payments/initiate",
        json={
            "booking_id": "test-booking-789",
            "amount": 150.00,
            "currency": "USD",
            "payment_method": "credit_card",
        },
    )
    payment_id = create_response.json()["payment_id"]

    # Confirm it
    response = client.post(f"/api/v1/payments/{payment_id}/confirm")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["payment_id"] == payment_id


def test_cancel_payment():
    """Test payment cancellation"""
    # Create a payment
    create_response = client.post(
        "/api/v1/payments/initiate",
        json={
            "booking_id": "test-booking-999",
            "amount": 75.00,
            "currency": "USD",
            "payment_method": "debit_card",
        },
    )
    payment_id = create_response.json()["payment_id"]

    # Cancel it
    response = client.post(f"/api/v1/payments/{payment_id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"
    assert data["payment_id"] == payment_id
