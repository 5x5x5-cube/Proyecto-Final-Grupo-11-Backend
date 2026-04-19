from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exceptions import InvalidTokenError, PaymentNotFoundError, TokenExpiredError
from .routers import gateway_router, payments_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Payment Service",
    description="Payment Processing Service",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)
app.include_router(gateway_router)


# --- Exception handlers ---


@app.exception_handler(PaymentNotFoundError)
async def payment_not_found_handler(request: Request, exc: PaymentNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"code": "PAYMENT_NOT_FOUND", "message": str(exc)},
    )


@app.exception_handler(InvalidTokenError)
async def invalid_token_handler(request: Request, exc: InvalidTokenError):
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_TOKEN", "message": str(exc)},
    )


@app.exception_handler(TokenExpiredError)
async def token_expired_handler(request: Request, exc: TokenExpiredError):
    return JSONResponse(
        status_code=400,
        content={"code": "TOKEN_EXPIRED", "message": str(exc)},
    )


# --- Health and root ---


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "payment-service", "version": "0.2.0"}


@app.get("/")
async def root():
    return {"service": "payment-service", "message": "Payment Processing Service"}
