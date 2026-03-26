import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "cart-service"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "cart-service"


def test_get_cart_missing_user_id():
    """GET /api/v1/cart without X-User-Id header returns 401."""
    response = client.get("/api/v1/cart")
    assert response.status_code == 401
    assert "Missing X-User-Id" in response.json()["detail"]


def test_get_cart_invalid_user_id():
    """GET /api/v1/cart with invalid UUID returns 401."""
    response = client.get("/api/v1/cart", headers={"X-User-Id": "not-a-uuid"})
    assert response.status_code == 401
    assert "Invalid X-User-Id" in response.json()["detail"]


def test_put_cart_missing_user_id():
    """PUT /api/v1/cart without X-User-Id header returns 401."""
    response = client.put(
        "/api/v1/cart",
        json={
            "roomId": str(uuid.uuid4()),
            "hotelId": str(uuid.uuid4()),
            "checkIn": "2026-04-01",
            "checkOut": "2026-04-03",
            "guests": 2,
        },
    )
    assert response.status_code == 401


def test_delete_cart_missing_user_id():
    """DELETE /api/v1/cart without X-User-Id header returns 401."""
    response = client.delete("/api/v1/cart")
    assert response.status_code == 401
