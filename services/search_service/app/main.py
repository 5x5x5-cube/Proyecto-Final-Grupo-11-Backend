from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import search_router, accommodations_router
from app.config import get_settings
from app.redis_client import redis_client

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Search Service - Search and filter accommodations with Redis",
    version=settings.app_version
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)
app.include_router(accommodations_router)

@app.on_event("startup")
async def startup_event():
    print(" Search Service starting up...")
    print(f" Redis connected: {settings.redis_url}")
    print(f" SQS Queue: {settings.sqs_queue_url}")

@app.get("/health")
async def health_check():
    try:
        redis_client.get_client().ping()
        redis_status = "connected"
    except:
        redis_status = "disconnected"
    
    return {
        "status": "healthy",
        "service": "search-service",
        "version": settings.app_version,
        "redis": redis_status
    }

@app.get("/")
async def root():
    return {
        "service": "search-service",
        "message": "Search Service",
        "version": settings.app_version,
        "endpoints": {
            "search": "/search",
            "suggestions": "/search/suggestions",
            "accommodation": "/accommodations/{id}",
            "health": "/health"
        }
    }
