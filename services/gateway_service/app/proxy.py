"""Generic async reverse proxy for forwarding requests to backend services."""

import logging

import httpx
from fastapi import Request
from fastapi.responses import Response

from .config import settings

logger = logging.getLogger(__name__)


async def proxy_request(request: Request, target_base_url: str) -> Response:
    """
    Forward an incoming request to a backend service, preserving:
    - HTTP method
    - Path (full path including /api/v1)
    - Query parameters
    - Headers (minus hop-by-hop headers)
    - Request body

    Returns the upstream response as-is.
    """
    # Build the target URL: base + original path + query string
    target_url = f"{target_base_url}{request.url.path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    # Read the request body
    body = await request.body()

    # Filter out hop-by-hop headers
    hop_by_hop = {"host", "connection", "keep-alive", "transfer-encoding", "te", "upgrade"}
    headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}

    # Inject default X-User-Id when no auth service exists yet
    if "x-user-id" not in headers and settings.default_user_id:
        headers["X-User-Id"] = settings.default_user_id

    # Inject default X-Hotel-Id when no auth service exists yet
    if "x-hotel-id" not in headers and settings.default_hotel_id:
        headers["X-Hotel-Id"] = settings.default_hotel_id

    logger.info(f"Proxying {request.method} {request.url.path} -> {target_url}")

    async with httpx.AsyncClient(timeout=30) as client:
        upstream_response = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body if body else None,
        )

    # Build response, preserving upstream status and body
    excluded_headers = {"content-encoding", "content-length", "transfer-encoding"}
    response_headers = {
        k: v for k, v in upstream_response.headers.items() if k.lower() not in excluded_headers
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
