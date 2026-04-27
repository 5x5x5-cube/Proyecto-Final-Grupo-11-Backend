from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app


def _mock_httpx_client(status_code=200, content=b'{"data": []}', headers=None):
    """Helper to create a mock httpx client for proxy tests."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content
    mock_response.headers = headers or {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_root():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "gateway-service"


async def test_unimplemented_service_returns_501():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/reports/summary")
    assert resp.status_code == 501
    assert resp.json()["code"] == "NOT_IMPLEMENTED"


@patch("app.config.settings.search_service_url", "http://search:8000")
@patch("app.proxy.httpx.AsyncClient")
async def test_public_route_proxies_without_token(mock_client_cls):
    """Public routes (search) should proxy without requiring a token."""
    mock_client_cls.return_value = _mock_httpx_client(content=b'[{"name": "Cartagena"}]')

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/search/destinations")
    assert resp.status_code == 200


@patch("app.proxy.httpx.AsyncClient")
@patch("app.proxy.resolve_traveler")
async def test_protected_route_proxies_with_valid_token(mock_resolve, mock_client_cls):
    """Protected routes should proxy when a valid token is provided."""
    mock_resolve.return_value = {"user_id": "user-123", "role": "traveler"}
    mock_client = _mock_httpx_client()
    mock_client_cls.return_value = mock_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/bookings",
            headers={"Authorization": "Bearer valid-token"},
        )
    assert resp.status_code == 200
    # Verify X-User-Id was injected in proxied headers
    call_kwargs = mock_client.request.call_args.kwargs
    req_headers = call_kwargs["headers"]
    assert req_headers["X-User-Id"] == "user-123"
    assert req_headers["X-User-Role"] == "traveler"


async def test_protected_route_returns_401_without_token():
    """Protected routes should return 401 when no token is provided."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/v1/bookings")
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


@patch("app.proxy.resolve_traveler")
async def test_protected_route_returns_401_with_invalid_token(mock_resolve):
    """Protected routes should return 401 when token is invalid."""
    mock_resolve.return_value = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(
            "/api/v1/bookings",
            headers={"Authorization": "Bearer bad-token"},
        )
    assert resp.status_code == 401
    assert "Invalid or expired token" in resp.json()["detail"]
