from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Auth Service", description="Authentication and Authorization Service", version="0.1.0"
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
    return {"status": "healthy", "service": "auth-service", "version": "0.1.0"}


@app.get("/")
async def root():
    return {"service": "auth-service", "message": "Authentication and Authorization Service"}
