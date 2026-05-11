from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/travelhub"

    aws_region: str = "us-east-1"
    aws_endpoint_url: Optional[str] = "http://localhost:4566"
    sqs_queue_url: str = "http://localhost:4566/000000000000/notification-queue"

    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    sqs_poll_interval: int = 20
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 300

    expo_access_token: Optional[str] = None
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"

    # SMTP settings for email notifications
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = False
    smtp_from_email: str = "noreply@travelhub.com"
    smtp_from_name: str = "TravelHub"

    # Service URLs for data enrichment
    auth_service_url: str = "http://localhost:8011"
    booking_service_url: str = "http://localhost:8002"
    payment_service_url: str = "http://localhost:8009"
    inventory_service_url: str = "http://localhost:8006"

    # Fraud alerts (HU4.7) — email address that receives fraud_detected
    # notifications. Leave empty to skip the email channel and rely on logs
    # + the payment_service /fraud-alerts endpoints instead.
    fraud_admin_email: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()


@lru_cache()
def get_settings() -> Settings:
    return Settings()
