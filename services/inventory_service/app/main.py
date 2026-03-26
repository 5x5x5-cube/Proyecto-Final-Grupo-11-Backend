from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import webhooks_router, accommodations_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="Inventory Management Service - Receives accommodations from third-party providers",
    version=settings.app_version
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router)
app.include_router(accommodations_router)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "inventory-service",
        "version": settings.app_version
    }

@app.get("/")
async def root():
    return {
        "service": "inventory-service",
        "message": "Inventory Management Service",
        "version": settings.app_version,
        "endpoints": {
            "webhooks": "/webhooks/accommodation",
            "accommodations": "/accommodations",
            "health": "/health"
        }
    }
