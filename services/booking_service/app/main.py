from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exceptions import BookingAlreadyProcessedError, BookingNotFoundError
from .routers import bookings, hotel_bookings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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

app.include_router(hotel_bookings.router)
app.include_router(bookings.router)


# --- Exception handlers ---


@app.exception_handler(BookingNotFoundError)
async def booking_not_found_handler(request: Request, exc: BookingNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "BOOKING_NOT_FOUND", "message": str(exc)},
    )


@app.exception_handler(BookingAlreadyProcessedError)
async def booking_already_processed_handler(request: Request, exc: BookingAlreadyProcessedError):
    return JSONResponse(
        status_code=409,
        content={"code": "BOOKING_ALREADY_PROCESSED", "message": str(exc)},
    )


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "booking-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "booking-service", "message": "Booking Management Service"}
