from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exceptions import (
    CartExpiredError,
    CartNotFoundError,
    InventoryServiceError,
    RoomUnavailableError,
)
from .redis_client import close_redis
from .routers import cart


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="Cart Service",
    description="Shopping Cart Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cart.router)


# --- Exception handlers ---


@app.exception_handler(CartNotFoundError)
async def cart_not_found_handler(request: Request, exc: CartNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "CART_NOT_FOUND", "message": str(exc)},
    )


@app.exception_handler(CartExpiredError)
async def cart_expired_handler(request: Request, exc: CartExpiredError):
    return JSONResponse(
        status_code=410,
        content={"code": "CART_EXPIRED", "message": str(exc)},
    )


@app.exception_handler(RoomUnavailableError)
async def room_unavailable_handler(request: Request, exc: RoomUnavailableError):
    return JSONResponse(
        status_code=409,
        content={"code": "ROOM_UNAVAILABLE", "message": str(exc)},
    )


@app.exception_handler(InventoryServiceError)
async def inventory_service_error_handler(request: Request, exc: InventoryServiceError):
    status = exc.status_code or 502
    return JSONResponse(
        status_code=status,
        content={"code": "INVENTORY_ERROR", "message": str(exc)},
    )


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "cart-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "cart-service", "message": "Shopping Cart Service"}
