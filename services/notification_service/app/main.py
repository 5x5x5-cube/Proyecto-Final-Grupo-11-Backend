from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Notification Service",
    description="Notification Service",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "notification-service",
        "version": "0.1.0"
    }

@app.get("/")
async def root():
    return {
        "service": "notification-service",
        "message": "Notification Service"
    }
