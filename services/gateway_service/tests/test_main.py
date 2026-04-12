from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "gateway-service"


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "gateway-service"


async def test_unimplemented_service_returns_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/auth/me")
    assert resp.status_code == 501
    assert resp.json()["code"] == "NOT_IMPLEMENTED"
    assert "auth" in resp.json()["message"]


async def test_unimplemented_search_returns_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/search/hotels")
    assert resp.status_code == 501


async def test_unimplemented_cart_returns_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/cart")
    assert resp.status_code == 501


async def test_unimplemented_payments_returns_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/payments", json={})
    assert resp.status_code == 501


@patch("app.proxy.httpx.AsyncClient")
async def test_proxy_forwards_to_booking_service(mock_client_cls):
    """Verify that /api/v1/bookings/* is proxied to the booking service."""
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'{"data": []}'
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/bookings?userId=abc-123")

    assert resp.status_code == 200
    # Verify the proxy called the correct upstream URL
    mock_client.request.assert_called_once()
    call_kwargs = mock_client.request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert "/api/v1/bookings" in call_kwargs.kwargs["url"]
    assert "userId=abc-123" in call_kwargs.kwargs["url"]


@patch("app.proxy.httpx.AsyncClient")
async def test_proxy_forwards_post_with_body(mock_client_cls):
    """Verify that POST body is forwarded to the backend service."""
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "test-id", "status": "pending"}'
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/bookings",
            json={"roomId": "123", "hotelId": "456"},
        )

    assert resp.status_code == 201
    call_kwargs = mock_client.request.call_args
    assert call_kwargs.kwargs["method"] == "POST"
    assert call_kwargs.kwargs["content"] is not None


@patch("app.proxy.httpx.AsyncClient")
async def test_proxy_preserves_upstream_error_status(mock_client_cls):
    """Verify that upstream 409 is returned as-is through the gateway."""
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.content = b'{"code": "ROOM_HELD", "message": "Room is held"}'
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client_cls.return_value = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/api/v1/bookings", json={})

    assert resp.status_code == 409
    assert resp.json()["code"] == "ROOM_HELD"
