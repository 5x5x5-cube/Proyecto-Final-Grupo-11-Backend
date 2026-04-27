import asyncio
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.redis_client import redis_client
from app.routes import search_router
from app.services.sqs_consumer import consumer

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Search Service - Search and filter accommodations with Redis",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)


def sqs_consumer_sync_loop():
    """Synchronous loop that polls SQS for messages. Runs in separate thread."""
    print("Starting SQS consumer loop (sync thread)...")
    while True:
        try:
            processed = consumer.poll_messages()
            if processed > 0:
                print(f"Processed {processed} SQS message(s)")
        except Exception as e:
            print(f"SQS consumer error: {e}")
            time.sleep(5)


async def start_sqs_consumer():
    """Start SQS consumer in a separate thread."""
    print("Starting SQS consumer in background thread...")
    loop = asyncio.get_event_loop()
    # Run the sync loop in a separate thread
    await loop.run_in_executor(None, sqs_consumer_sync_loop)


@app.on_event("startup")
async def startup_event():
    print("Search Service starting up...")
    print(f"Redis connected: {settings.redis_url}")
    print(f"SQS Queue: {settings.sqs_queue_url}")
    # Start SQS consumer as background task in separate thread
    asyncio.create_task(start_sqs_consumer())


@app.get("/health")
async def health_check():
    try:
        redis_client.get_client().ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    return {
        "status": "healthy",
        "service": "search-service",
        "version": settings.app_version,
        "redis": redis_status,
    }


@app.get("/")
async def root():
    return {
        "service": "search-service",
        "message": "Hotel Search Service",
        "version": settings.app_version,
        "endpoints": {
            "get_destinations": "/api/v1/search/destinations",
            "search_hotels": "/api/v1/search/hotels",
            "get_rooms": "/api/v1/search/hotels/{hotel_id}/rooms",
            "health": "/health",
            "root": "/",
        },
    }
