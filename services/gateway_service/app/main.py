import logging
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_service_routes
from .proxy import proxy_request

logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Gateway",
    description="TravelHub API Gateway",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Regex to extract the service prefix from /api/v1/{service}/...
API_PATH_PATTERN = re.compile(r"^/api/v1/([^/]+)")


@app.api_route(
    "/api/v1/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def gateway_proxy(request: Request, path: str):
    """
    Main gateway route — matches all /api/v1/* requests and proxies
    them to the appropriate backend service based on the first path segment.
    """
    match = API_PATH_PATTERN.match(request.url.path)
    if not match:
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_PATH", "message": "Invalid API path"},
        )

    service_prefix = match.group(1)
    routes = get_service_routes()
    target_url = routes.get(service_prefix)

    if target_url is None:
        return JSONResponse(
            status_code=501,
            content={
                "code": "NOT_IMPLEMENTED",
                "message": f"Service '{service_prefix}' is not yet implemented",
            },
        )

    return await proxy_request(request, target_url)


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "gateway-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "gateway-service", "message": "TravelHub API Gateway"}
