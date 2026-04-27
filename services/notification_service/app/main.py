import logging
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import notifications
from .services.sqs_consumer import consumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Notification Service", description="Notification Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(notifications.router)


# SQS Consumer thread
def sqs_consumer_loop():
    """Background thread to consume SQS messages."""
    logger.info("Starting SQS consumer thread...")
    while True:
        try:
            processed = consumer.poll_messages()
            if processed > 0:
                logger.info(f"Processed {processed} messages from SQS")
        except Exception as e:
            logger.error(f"Error in SQS consumer loop: {e}")
        time.sleep(1)  # Small delay between polls


@app.on_event("startup")
async def startup_event():
    """Start SQS consumer thread on app startup."""
    consumer_thread = threading.Thread(target=sqs_consumer_loop, daemon=True)
    consumer_thread.start()
    logger.info("SQS consumer thread started")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "notification-service", "version": "0.2.0"}


@app.get("/")
async def root():
    return {"service": "notification-service", "message": "Notification Service"}
