import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exceptions import HoldNotFoundError, RoomHeldError, RoomNotFoundError, RoomUnavailableError
from .redis_client import close_redis
from .routers import holds, hotels, rooms
from .tasks.cleanup import cleanup_expired_holds_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch background cleanup task
    cleanup_task = asyncio.create_task(cleanup_expired_holds_loop())
    yield
    # Shutdown: cancel cleanup and close Redis
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_redis()


app = FastAPI(
    title="Inventory Service",
    description="Inventory Management Service",
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

app.include_router(hotels.router)
app.include_router(rooms.router)
app.include_router(holds.router)


# --- Exception handlers ---


@app.exception_handler(RoomNotFoundError)
async def room_not_found_handler(request: Request, exc: RoomNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "ROOM_NOT_FOUND", "message": str(exc)},
    )


@app.exception_handler(RoomUnavailableError)
async def room_unavailable_handler(request: Request, exc: RoomUnavailableError):
    return JSONResponse(
        status_code=409,
        content={
            "code": "ROOM_UNAVAILABLE",
            "message": str(exc),
            "details": [{"dates": exc.dates}] if exc.dates else None,
        },
    )


@app.exception_handler(RoomHeldError)
async def room_held_handler(request: Request, exc: RoomHeldError):
    return JSONResponse(
        status_code=409,
        content={"code": "ROOM_HELD", "message": str(exc)},
    )


@app.exception_handler(HoldNotFoundError)
async def hold_not_found_handler(request: Request, exc: HoldNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "HOLD_NOT_FOUND", "message": str(exc)},
    )


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "inventory-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {
        "service": "inventory-service",
        "message": "Inventory Management Service",
        "version": "0.1.0",
        "endpoints": {
            "register_hotel": "POST /hotels/webhook",
            "list_hotels": "GET /hotels",
            "get_hotel": "GET /hotels/{hotel_id}",
            "get_room": "GET /rooms/{room_id}",
            "get_room_hotel": "GET /rooms/{room_id}/hotel",
            "get_room_availability": "GET /rooms/{room_id}/availability?checkIn=&checkOut=",
            "create_hold": "POST /holds",
            "release_hold": "DELETE /holds/{hold_id}",
            "get_hold": "GET /holds/{hold_id}",
            "check_hold": "GET /holds/check/{room_id}?checkIn=&checkOut=",
            "health": "GET /health",
        },
    }
