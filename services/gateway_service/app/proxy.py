"""Async reverse proxy with auth resolution for the API gateway."""

import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response

from .auth import resolve_hotel_admin, resolve_traveler
from .config import settings
from .route_config import AuthMode, get_auth_mode

logger = logging.getLogger(__name__)

# Headers the client must never set — only the gateway injects these.
STRIPPED_HEADERS = {"x-user-id", "x-hotel-id", "x-user-role"}
HOP_BY_HOP = {"host", "connection", "keep-alive", "transfer-encoding", "te", "upgrade"}


def _extract_bearer_token(headers: dict[str, str]) -> str | None:
    auth = headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


async def proxy_request(request: Request, target_base_url: str) -> Response:
    """Forward a request to a backend service with auth resolution."""
    target_url = f"{target_base_url}{request.url.path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    body = await request.body()

    # Build headers: strip hop-by-hop and identity headers
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() not in STRIPPED_HEADERS
    }

    # --- Auth resolution ---
    mode = get_auth_mode(request.method, request.url.path)
    token = _extract_bearer_token(dict(request.headers))

    if mode == AuthMode.TRAVELER:
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        user = await resolve_traveler(token, settings.auth_service_url)
        if not user:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})
        headers["X-User-Id"] = user["user_id"]
        headers["X-User-Role"] = user["role"]

    elif mode == AuthMode.HOTEL_ADMIN:
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})
        admin = await resolve_hotel_admin(
            token, settings.auth_service_url, settings.inventory_service_url
        )
        if not admin:
            return JSONResponse(
                status_code=403,
                content={"detail": "Hotel admin access required"},
            )
        headers["X-User-Id"] = admin["user_id"]
        headers["X-User-Role"] = admin["role"]
        headers["X-Hotel-Id"] = admin["hotel_id"]

    elif mode == AuthMode.OPTIONAL_AUTH:
        if token:
            user = await resolve_traveler(token, settings.auth_service_url)
            if user:
                headers["X-User-Id"] = user["user_id"]
                headers["X-User-Role"] = user["role"]

    # PUBLIC mode: no auth processing

    logger.info("Proxying %s %s -> %s [%s]", request.method, request.url.path, target_url, mode)

    async with httpx.AsyncClient(timeout=30) as client:
        upstream_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )

    excluded_headers = {"content-encoding", "content-length", "transfer-encoding"}
    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() not in excluded_headers
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
