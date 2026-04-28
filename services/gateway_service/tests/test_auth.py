"""Tests for gateway auth resolution and header injection."""

from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.auth import resolve_hotel_admin, resolve_traveler
from app.main import app
from app.route_config import AuthMode, get_auth_mode

# --- route_config tests ---


class TestRouteConfig:
    def test_auth_routes_are_public(self):
        assert get_auth_mode("POST", "/api/v1/auth/login") == AuthMode.PUBLIC
        assert get_auth_mode("POST", "/api/v1/auth/register") == AuthMode.PUBLIC
        assert get_auth_mode("GET", "/api/v1/auth/me") == AuthMode.PUBLIC

    def test_search_routes_are_public(self):
        assert get_auth_mode("GET", "/api/v1/search/destinations") == AuthMode.PUBLIC
        assert get_auth_mode("GET", "/api/v1/search/hotels") == AuthMode.PUBLIC

    def test_inventory_routes_mostly_public(self):
        assert get_auth_mode("GET", "/api/v1/inventory/hotels") == AuthMode.PUBLIC
        assert get_auth_mode("GET", "/api/v1/inventory/rooms") == AuthMode.PUBLIC

    def test_inventory_holds_are_protected(self):
        assert get_auth_mode("POST", "/api/v1/inventory/holds") == AuthMode.TRAVELER
        assert get_auth_mode("GET", "/api/v1/inventory/holds/check/room-123") == AuthMode.TRAVELER

    def test_inventory_tariffs_are_hotel_admin(self):
        assert get_auth_mode("GET", "/api/v1/inventory/tariffs/admin/rooms") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("GET", "/api/v1/inventory/tariffs") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("POST", "/api/v1/inventory/tariffs") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("PUT", "/api/v1/inventory/tariffs/t-1") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("DELETE", "/api/v1/inventory/tariffs/t-1") == AuthMode.HOTEL_ADMIN

    def test_booking_list_and_create_are_traveler(self):
        assert get_auth_mode("GET", "/api/v1/bookings") == AuthMode.TRAVELER
        assert get_auth_mode("POST", "/api/v1/bookings") == AuthMode.TRAVELER

    def test_booking_detail_is_public(self):
        assert get_auth_mode("GET", "/api/v1/bookings/abc-123") == AuthMode.PUBLIC

    def test_booking_qr_is_traveler(self):
        assert get_auth_mode("GET", "/api/v1/bookings/abc-123/qr") == AuthMode.TRAVELER

    def test_booking_hotel_routes_are_hotel_admin(self):
        assert get_auth_mode("GET", "/api/v1/bookings/hotel/") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("POST", "/api/v1/bookings/hotel/abc/status") == AuthMode.HOTEL_ADMIN

    def test_payments_initiate_is_traveler(self):
        assert get_auth_mode("POST", "/api/v1/payments/initiate") == AuthMode.TRAVELER

    def test_payments_other_are_public(self):
        assert get_auth_mode("GET", "/api/v1/payments/exchange-rates") == AuthMode.PUBLIC
        assert get_auth_mode("GET", "/api/v1/payments/pay-123") == AuthMode.PUBLIC

    def test_cart_is_traveler(self):
        assert get_auth_mode("GET", "/api/v1/cart") == AuthMode.TRAVELER
        assert get_auth_mode("PUT", "/api/v1/cart") == AuthMode.TRAVELER

    def test_notifications_are_traveler(self):
        assert get_auth_mode("GET", "/api/v1/notifications/history") == AuthMode.TRAVELER

    def test_reports_are_hotel_admin(self):
        assert get_auth_mode("GET", "/api/v1/reports/dashboard") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("GET", "/api/v1/reports/kpis") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("GET", "/api/v1/reports/revenue") == AuthMode.HOTEL_ADMIN
        assert get_auth_mode("GET", "/api/v1/reports/transactions") == AuthMode.HOTEL_ADMIN

    def test_bookings_discounts_are_hotel_admin(self):
        assert get_auth_mode("GET", "/api/v1/bookings/discounts") == AuthMode.HOTEL_ADMIN

    def test_unknown_route_defaults_to_traveler(self):
        assert get_auth_mode("GET", "/api/v1/unknown/stuff") == AuthMode.TRAVELER


# --- resolve_traveler tests ---


def _mock_httpx_response(status_code, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    return resp


class TestResolveTraveler:
    @patch("app.auth.httpx.AsyncClient")
    async def test_returns_user_on_success(self, mock_cls):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_httpx_response(
            200, {"user_id": "u-1", "email": "a@b.com", "name": "A", "role": "traveler"}
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await resolve_traveler("tok", "http://auth:8000")
        assert result == {"user_id": "u-1", "role": "traveler"}

    @patch("app.auth.httpx.AsyncClient")
    async def test_returns_none_on_401(self, mock_cls):
        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_httpx_response(401)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await resolve_traveler("bad", "http://auth:8000")
        assert result is None

    @patch("app.auth.httpx.AsyncClient")
    async def test_returns_none_on_network_error(self, mock_cls):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await resolve_traveler("tok", "http://auth:8000")
        assert result is None


# --- resolve_hotel_admin tests ---


class TestResolveHotelAdmin:
    @patch("app.auth.httpx.AsyncClient")
    @patch("app.auth.resolve_traveler")
    async def test_returns_admin_with_hotel(self, mock_resolve, mock_cls):
        mock_resolve.return_value = {"user_id": "admin-1", "role": "hotel_admin"}

        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_httpx_response(
            200, [{"id": "hotel-abc", "name": "Hotel Test"}]
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await resolve_hotel_admin("tok", "http://auth:8000", "http://inv:8000")
        assert result == {
            "user_id": "admin-1",
            "role": "hotel_admin",
            "hotel_id": "hotel-abc",
        }

    @patch("app.auth.resolve_traveler")
    async def test_returns_none_for_non_admin(self, mock_resolve):
        mock_resolve.return_value = {"user_id": "u-1", "role": "traveler"}

        result = await resolve_hotel_admin("tok", "http://auth:8000", "http://inv:8000")
        assert result is None

    @patch("app.auth.resolve_traveler")
    async def test_returns_none_on_invalid_token(self, mock_resolve):
        mock_resolve.return_value = None

        result = await resolve_hotel_admin("bad", "http://auth:8000", "http://inv:8000")
        assert result is None

    @patch("app.auth.httpx.AsyncClient")
    @patch("app.auth.resolve_traveler")
    async def test_returns_none_when_no_hotel_found(self, mock_resolve, mock_cls):
        mock_resolve.return_value = {"user_id": "admin-1", "role": "hotel_admin"}

        mock_client = AsyncMock()
        mock_client.get.return_value = _mock_httpx_response(200, [])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client

        result = await resolve_hotel_admin("tok", "http://auth:8000", "http://inv:8000")
        assert result is None


# --- Integration: header stripping ---


def _mock_proxy_client(status_code=200, content=b"{}"):
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content
    mock_response.headers = {"content-type": "application/json"}

    mock_client = AsyncMock()
    mock_client.request.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestHeaderStripping:
    @patch("app.proxy.httpx.AsyncClient")
    @patch("app.proxy.resolve_traveler")
    async def test_client_x_user_id_is_stripped(self, mock_resolve, mock_client_cls):
        """Client-sent X-User-Id must be stripped to prevent forgery."""
        mock_resolve.return_value = {"user_id": "real-user", "role": "traveler"}
        mock_client = _mock_proxy_client()
        mock_client_cls.return_value = mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/bookings",
                headers={
                    "Authorization": "Bearer valid",
                    "X-User-Id": "forged-evil-id",
                },
            )

        assert resp.status_code == 200
        proxied_headers = mock_client.request.call_args.kwargs["headers"]
        assert proxied_headers["X-User-Id"] == "real-user"
        assert proxied_headers["X-User-Id"] != "forged-evil-id"

    @patch("app.config.settings.search_service_url", "http://search:8000")
    @patch("app.proxy.httpx.AsyncClient")
    async def test_public_route_strips_x_user_id(self, mock_client_cls):
        """Even on public routes, client-sent X-User-Id is stripped."""
        mock_client = _mock_proxy_client()
        mock_client_cls.return_value = mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/search/destinations",
                headers={"X-User-Id": "forged-id"},
            )

        assert resp.status_code == 200
        proxied_headers = mock_client.request.call_args.kwargs["headers"]
        assert "X-User-Id" not in proxied_headers

    @patch("app.proxy.httpx.AsyncClient")
    @patch("app.proxy.resolve_hotel_admin")
    async def test_hotel_admin_gets_hotel_id_injected(self, mock_resolve, mock_client_cls):
        """Hotel admin routes should have X-Hotel-Id injected by the gateway."""
        mock_resolve.return_value = {
            "user_id": "admin-1",
            "role": "hotel_admin",
            "hotel_id": "hotel-abc",
        }
        mock_client = _mock_proxy_client()
        mock_client_cls.return_value = mock_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/bookings/hotel/",
                headers={"Authorization": "Bearer admin-token"},
            )

        assert resp.status_code == 200
        proxied_headers = mock_client.request.call_args.kwargs["headers"]
        assert proxied_headers["X-Hotel-Id"] == "hotel-abc"
        assert proxied_headers["X-User-Id"] == "admin-1"

    @patch("app.proxy.resolve_hotel_admin")
    async def test_non_admin_gets_403_on_hotel_route(self, mock_resolve):
        """Non-admin users should get 403 on hotel admin routes."""
        mock_resolve.return_value = None

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get(
                "/api/v1/bookings/hotel/",
                headers={"Authorization": "Bearer traveler-token"},
            )

        assert resp.status_code == 403
        assert "Hotel admin access required" in resp.json()["detail"]
