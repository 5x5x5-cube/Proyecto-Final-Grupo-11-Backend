from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import payments_router

app = FastAPI(title="Payment Service", description="Payment Processing Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "payment-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "payment-service", "message": "Payment Processing Service"}
