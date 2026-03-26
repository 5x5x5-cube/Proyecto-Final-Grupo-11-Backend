from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exceptions import BookingNotFoundError, InventoryServiceError
from .redis_client import close_redis
from .redis_lock import LockAcquisitionError
from .routers import bookings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="Booking Service",
    description="Booking Management Service",
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

app.include_router(bookings.router)


# --- Exception handlers ---


@app.exception_handler(BookingNotFoundError)
async def booking_not_found_handler(request: Request, exc: BookingNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "BOOKING_NOT_FOUND", "message": str(exc)},
    )


@app.exception_handler(InventoryServiceError)
async def inventory_service_error_handler(request: Request, exc: InventoryServiceError):
    status = exc.status_code or 502
    return JSONResponse(
        status_code=status,
        content={"code": "INVENTORY_ERROR", "message": str(exc)},
    )


@app.exception_handler(LockAcquisitionError)
async def lock_error_handler(request: Request, exc: LockAcquisitionError):
    return JSONResponse(
        status_code=503,
        content={"code": "SERVICE_BUSY", "message": "Server busy, please try again"},
    )


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "booking-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "booking-service", "message": "Booking Management Service"}
