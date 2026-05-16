from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import revenue

app = FastAPI(title="Reports Service", description="Reports Generation Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(revenue.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "reports-service", "version": "0.2.0"}


@app.get("/")
async def root():
    return {
        "service": "reports-service",
        "message": "Reports Generation Service",
        "version": "0.2.0",
        "endpoints": {
            "monthly_revenue": "/api/v1/reports/revenue/monthly",
            "available_periods": "/api/v1/reports/revenue/available-periods",
            "download_report": "/api/v1/reports/revenue/download",
            "health": "/health",
        },
    }
